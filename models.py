from sqlalchemy import Column, Integer, String, Float
from database import Base

class SensorData(Base):
    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_id = Column(String, index=True)
    temperature = Column(Float)
    humidity = Column(Float)
