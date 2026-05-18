from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageMessage
from PIL import Image, ImageOps
import numpy as np
import os
import tensorflow as tf
from google import genai
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyADD6S9tPlbAXXCElffpOkh6_d8MCwEidE")
ai_client = genai.Client(api_key=GEMINI_KEY)
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
             "4 ข้าวต้ม": "200-300",
             "5 ไอศกรีม": "140-250",
             "6 ราดหน้า": "400-600",
             "7 ข้าวกะเพราไข่ดาว": "600-750",
             "8 สุกี้น้ำ": "300-400",
             "9 สุกี้แห้ง": "400-500",
             "10 ข้าวผัด": "500-700",
             "11 ส้มตำ": "120-250",
             "12 เฟรนช์ฟราย": "300-400",
             "13 นักเก็ต": "250-350",
             "14 ข้าวไข่เจียว": "450-600",
             "15 ข้่าวไข่เจียวทรงเครื่อง": "500-700",
             "16 เฉาก๊วยนมสด": "150-250",
             "17 นม": "70-150",
             "18 บราวนี่": "250-350",
             "19 เครปเย็น": "300-500",
             "20 เค้ก": "250-400",
             "21 มะม่วง": "100-150",
             "22 ส้ม": "60-80",
             "23 สตรอว์เบอร์รี่": "30-50",
             "24 ชมพู่": "30-50",
             "25 องุ่น": "60-80",
             "26 ข้าวหมูแดง": "500-600",
             "27 ข้าวหมูกรอบ": "600-800",
             "28 ข้าวเหนียวหมูหยอง": "300-450",
             "29 ข้าวเหนียวไก่ทอด": "450-700"
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
try:
        system_prompt = (
            "คุณคือผู้เชี่ยวชาญด้านอาหารและสุขภาพที่ใจดี เป็นมิตร และพูดจาไพเราะ (ลงท้ายด้วย ค่ะ/นะคะ) "
            "มีหน้าที่ตอบคำถาม คุยเล่น และให้คำแนะนำเรื่องอาหารการกินกับผู้ใช้ "
            "กฎเหล็ก: ให้แนะนำอาหารในแง่ดี สร้างสรรค์ น่ากิน แต่ต้องคอยเตือนเรื่องที่ควรเตือนอย่างประนีประนอม "
            "(เช่น หากผู้ใช้บอกว่าอยากกินของหวาน ให้แนะนำเมนูที่อร่อยแต่เตือนเรื่องปริมาณน้ำตาล หรือเสนอทางเลือกสุขภาพที่อร่อยไม่แพ้กัน) "
            "เน้นการให้กำลังใจ ไม่พูดให้ผู้ใช้รู้สึกผิด และตอบคำถามทั่วไปอื่นๆ ได้อย่างเป็นธรรมชาติ"
        )
        
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=text,
            config={'system_instruction': system_prompt}
        )
        
        reply_text = response.text
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        
    except Exception as e:
        print(f"Gemini Error: {e}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="ขออภัยด้วยนะคะ ระบบประมวลผลข้อความขัดข้องชั่วคราวค่ะ"))
