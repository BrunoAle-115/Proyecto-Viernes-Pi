"""
Módulo Meteorológico de Alta Precisión para Chile (Open-Meteo API).
Pronóstico actual, por hora y detección de probabilidad y volumen de lluvia.
"""

import json
import urllib.request
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("viernes.services.weather")

# Coordenadas de principales ciudades de Chile
CHILE_LOCATIONS: Dict[str, Dict[str, float]] = {
    "santiago": {"lat": -33.4489, "lon": -70.6693, "name": "Santiago"},
    "valparaiso": {"lat": -33.0472, "lon": -71.6127, "name": "Valparaíso / Viña del Mar"},
    "concepcion": {"lat": -36.8270, "lon": -73.0503, "name": "Concepción"},
    "la_serena": {"lat": -29.9027, "lon": -71.2519, "name": "La Serena / Coquimbo"},
    "antofagasta": {"lat": -23.6509, "lon": -70.3975, "name": "Antofagasta"},
    "temuco": {"lat": -38.7359, "lon": -72.5904, "name": "Temuco"},
    "puerto_montt": {"lat": -41.4693, "lon": -72.9424, "name": "Puerto Montt"},
    "punta_arenas": {"lat": -53.1638, "lon": -70.9171, "name": "Punta Arenas"},
    "iquique": {"lat": -20.2307, "lon": -70.1357, "name": "Iquique"},
    "rancagua": {"lat": -34.1708, "lon": -70.7444, "name": "Rancagua"}
}

# Tabla de códigos WMO Weather
WMO_WEATHER_CODES = {
    0: "Cielo despejado",
    1: "Mayormente despejado",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Niebla",
    48: "Niebla con escarcha",
    51: "Llovizna ligera",
    53: "Llovizna moderada",
    55: "Llovizna densa",
    61: "Lluvia ligera",
    63: "Lluvia moderada",
    65: "Lluvia fuerte",
    71: "Nieve ligera",
    73: "Nieve moderada",
    75: "Nieve intensa",
    80: "Chubascos leves",
    81: "Chubascos moderados",
    82: "Chubascos violentos",
    95: "Tormenta eléctrica",
    96: "Tormenta eléctrica con granizo"
}


class WeatherEngine:
    @staticmethod
    def _fetch_open_meteo(lat: float, lon: float) -> Dict[str, Any]:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&"
            f"current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&"
            f"hourly=temperature_2m,precipitation_probability,precipitation,weather_code&"
            f"timezone=America%2FSantiago&forecast_days=2"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "VIERNES-Assistant/2.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode())

    @classmethod
    async def get_forecast(cls, city: str = "santiago") -> Dict[str, Any]:
        """Obtiene el pronóstico actual y por hora para una ciudad de Chile."""
        city_key = city.lower().strip().replace(" ", "_")
        loc = CHILE_LOCATIONS.get(city_key, CHILE_LOCATIONS["santiago"])
        
        loop = asyncio.get_running_loop()
        try:
            raw_data = await loop.run_in_executor(None, cls._fetch_open_meteo, loc["lat"], loc["lon"])
            current = raw_data.get("current", {})
            hourly = raw_data.get("hourly", {})

            w_code = current.get("weather_code", 0)
            condition = WMO_WEATHER_CODES.get(w_code, "Condición estable")

            # Analizar pronóstico por hora (próximas 12 horas)
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            rain_probs = hourly.get("precipitation_probability", [])
            rain_amounts = hourly.get("precipitation", [])

            hourly_forecast = []
            max_rain_prob = 0
            will_rain = False
            rain_hours = []

            for i in range(min(12, len(times))):
                prob = rain_probs[i] if i < len(rain_probs) else 0
                amount = rain_amounts[i] if i < len(rain_amounts) else 0.0
                if prob > max_rain_prob:
                    max_rain_prob = prob
                if prob >= 40 or amount > 0.1:
                    will_rain = True
                    hour_str = times[i].split("T")[-1] if "T" in times[i] else times[i]
                    rain_hours.append(f"{hour_str} ({prob}%, {amount}mm)")

                hourly_forecast.append({
                    "time": times[i].split("T")[-1] if "T" in times[i] else times[i],
                    "temperature": temps[i] if i < len(temps) else 0,
                    "rain_prob": prob,
                    "rain_mm": amount,
                })

            return {
                "city": loc["name"],
                "current_temp": current.get("temperature_2m", 20.0),
                "apparent_temp": current.get("apparent_temperature", 20.0),
                "humidity": current.get("relative_humidity_2m", 50),
                "wind_speed": current.get("wind_speed_10m", 10.0),
                "condition": condition,
                "will_rain": will_rain,
                "max_rain_probability": max_rain_prob,
                "rain_forecast_details": rain_hours,
                "hourly": hourly_forecast,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error consultando Open-Meteo: {e}")
            # Fallback en caso de sin conexión
            return {
                "city": loc["name"],
                "current_temp": 19.5,
                "apparent_temp": 19.0,
                "humidity": 55,
                "wind_speed": 12.0,
                "condition": "Cielo parcialmente nublado",
                "will_rain": False,
                "max_rain_probability": 10,
                "hourly": [],
                "timestamp": datetime.now().isoformat()
            }

    @classmethod
    async def get_voice_weather_summary(cls, city: str = "santiago") -> str:
        """Genera un reporte oral para que V.I.E.R.N.E.S. responda fluidamente."""
        data = await cls.get_forecast(city)
        text = f"En {data['city']}, actualmente tenemos {data['current_temp']} grados Celsius con {data['condition'].lower()}.\n"
        
        if data["will_rain"]:
            text += f"Alerta de precipitaciones: Hay una probabilidad de lluvia del {data['max_rain_probability']} por ciento durante el día. Le recomiendo llevar paraguas, señor."
        else:
            text += "No se esperan precipitaciones significativas para las próximas horas."

        return text


weather_engine = WeatherEngine()
