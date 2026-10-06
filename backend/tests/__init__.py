"""Isolamento dei test dall'ambiente di chi li lancia.

Questo file viene eseguito PRIMA di tutto il resto: le variabili d'ambiente (per esempio le chiavi di
Mailjet esportate nel terminale) e il file `backend/.env` non devono mai influenzare i test, e i test non
devono mai poter contattare servizi reali.
"""

import os

from app.core.config import Settings

Settings.model_config["env_file"] = None  # i test non leggono mai backend/.env
for (
    _name
) in Settings.model_fields:  # ...né le variabili d'ambiente che corrispondono alle impostazioni
    os.environ.pop(_name.upper(), None)
