from fastapi import FastAPI, Depends
# from fastapi_mqtt import FastMQTT, MQTTConfig
from sqlalchemy.orm import Session
from pydantic import BaseModel
import models
from database import SessionLocal, engine

# Initialize FastAPI app

app = FastAPI()


# Create DB tables
models.Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def read_root():
    return {"Hello": "World"}


# Pydantic input schema
class SensorIn(BaseModel):
    device_id: str
    temperature: float
    humidity: float
    
    
    

@app.post("/sensor-data/")
def create_sensor_data(data: SensorIn, db: Session = Depends(get_db)):
    sensor = models.SensorData(
        device_id=data.device_id,
        temperature=data.temperature,
        humidity=data.humidity
    )
    db.add(sensor)
    db.commit()
    db.refresh(sensor)
    return {
        "id": sensor.id,
        "recommendation": "Cool down" if sensor.temperature > 30 else "Stable"
    }

@app.get("/sensor-data/")
def read_sensor_data(db: Session = Depends(get_db)):
    sensors = db.query(models.SensorData).all()

    results = [
        {
            "id": s.id,
            "device_id": s.device_id,
            "temperature": s.temperature,
            "humidity": s.humidity
        }
        for s in sensors
    ]
    
    return results

# mqtt_config = MQTTConfig(host ='localhost', port = 1883, keepalive = 60)
# mqtt = FastMQTT(config=mqtt_config)
# mqtt.init_app(app)


# @mqtt.on_connect()
# def connect(client, flags, rc, properties):
#     print("Connected with result code %s" % rc)
#     mqtt.subscribe("sensor/data")

# @mqtt.on_message()
# def message(client, topic, payload, qos, properties):
#     print("Received message '%s' on topic '%s' with QoS %d" % (payload.decode(), topic, qos))