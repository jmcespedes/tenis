from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def home():
    return 'Aplicación en funcionamiento!'

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Usa el puerto de la variable de entorno o 5000 como predeterminado
    app.run(host='0.0.0.0', port=port)

    