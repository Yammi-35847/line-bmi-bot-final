from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageMessage
from PIL import Image, ImageOps
import numpy as np
import os
import tensorflow as tf

app = Flask(__name__)

# ตั้งค่า LINE API
line_bot_api = LineBotApi("fkzpG65r65ziCzYSFVzgYTkUkHcEY9kA2g+Q0AEQXyedgFeVIYEDSalRQoPblZlIHFqWTla6zTucQm226FAt6/vhTXqVuUxa/1Ebpjoq7T65QhkoadXnmcobyyR3IXqQwiJdi2xX8j6vz0s7u8tspgdB04t89/1O/w1cDnyilFU=")
handler = WebhookHandler("703a0d03e0a710133195e50703972a2e")

model = None

def load_model():
    global model
    if model is None:
        # โหลดโมเดล (ต้องมั่นใจว่าชื่อไฟล์ใน Replit คือ keras_model.h5)
        model = tf.keras.models.load_model("keras_model.h5")

# โหลด Labels จากไฟล์
with open("labels.txt", "r", encoding="utf-8") as f:
    labels = [line.strip() for line in f.readlines()]

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['x-line-signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 1. จัดการข้อความ (BMI)
@handler.add(MessageEvent, message=TextMessage) 
def handler_text_message(event):
    text = event.message.text
    if "น้ำหนัก" in text and "ส่วนสูง" in text:
         try:
             # คาดหวังรูปแบบ: น้ำหนัก 70 ส่วนสูง 170
             parts = text.split()
             w = float(parts[1])
             h = float(parts[3])
             h_meter = h / 100
             bmi = w / (h_meter**2)
             
             result = f"BMI ของคุณ {bmi:.2f}\n"
             if bmi < 18.5:
                 advice = "ค่า BMI ของคุณต่ำกว่าเกณฑ์นะคะ ควรเน้นโปรตีนและคาร์โบไฮเดรตค่ะ เช่น ข้าวผัดหมู แซนวิชไข่"
             elif bmi < 23:
                 advice = "ค่า BMI ของคุณอยู่ในเกณฑ์ปกตินะคะ รักษามาตรฐานนี้ไว้นะคะ"
             else:
                 advice = "ค่า BMI ของคุณสูงกว่าเกณฑ์นะคะ ควรเลี่ยงของทอดและของหวาน แนะนำอาหารไขมันต่ำ เช่น ต้มจืดค่ะ"
             
             line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result + advice))
         except Exception:
             line_bot_api.reply_message(event.reply_token, TextSendMessage(text="กรุณาพิมพ์ในรูปแบบ: น้ำหนัก 70 ส่วนสูง 170"))

# 2. จัดการรูปภาพ (AI Food Scanner)
@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    try:
        # ดึงรูปจาก LINE และบันทึก
        message_content = line_bot_api.get_message_content(event.message.id)
        with open("temp_image.jpg", "wb") as f:
            for chunk in message_content.iter_content():
                f.write(chunk)
        
        # ประมวลผลรูปภาพ
        image = Image.open("temp_image.jpg").convert("RGB")
        size = (224, 224)
        image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
        image_array = np.asarray(image)
        normalized_image_array = (image_array.astype(np.float32) / 127.0) - 1
        
        data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
        data[0] = normalized_image_array
        
        # ทำนายผล
        load_model()
        prediction = model.predict(data)
        index = np.argmax(prediction)
        food_name = labels[index].strip()
        
        # ฐานข้อมูลแคลอรี่ (Key ต้องตรงกับ labels.txt)
        calories_db = {
             "0 ก๋วยเตี๋ยว": "330-350", 
             "1 ข้าวมันไก่ต้ม": "539-619", 
             "2 ข้าวมันไก่ทอด": "693-800", 
             "3 ข้าวกะเพรา": "580-630", 
             "4 ข้าวต้ม": "200-300"
        }
        
        cal = calories_db.get(food_name, "ไม่ทราบข้อมูล")
        # ตัดเลขลำดับหน้าชื่ออาหารออก (เช่น "0 ก๋วยเตี๋ยว" -> "ก๋วยเตี๋ยว")
        display_name = food_name.split(' ', 1)[-1] if ' ' in food_name else food_name
        
        reply = f"วิเคราะห์ว่าเป็น: {display_name}\nพลังงานโดยประมาณ: {cal} kcal"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        
    except Exception as e:
        print(f"Error: {e}")
        # กรณี Error มักเกิดจาก RAM ไม่พอใน Replit ฟรี
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="ขออภัย ระบบประมวลผลรูปภาพขัดข้องชั่วคราวค่ะ"))

if __name__ == "__main__":
     port = int(os.environ.get("PORT", 5000))
     app.run(host='0.0.0.0', port=port)
