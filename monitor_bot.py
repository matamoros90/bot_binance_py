#!/usr/bin/env python3
"""
=============================================================
  WATCHDOG 24/7 — Bot Binance IA
=============================================================
  Mantiene bot_binance.py corriendo indefinidamente.
  Auto-reinicio inteligente con límite de crashes por hora.

  USO:
    python watchdog.py            ← Arranque normal 24/7
    python watchdog.py --once     ← Solo ejecutar bot (sin watchdog)
=============================================================
"""

import os
import sys
import time
import subprocess
import logging
from datetime import datetime, timedelta
from collections import deque

# ─── Logging del watchdog ────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WATCHDOG] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/watchdog.log", mode="a"),
    ]
)
logger = logging.getLogger("watchdog")

# ─── Configuración ───────────────────────────────────────
MAX_REINICIOS_POR_HORA = 5
DELAY_REINICIO_SEG     = 10     # Espera antes de reiniciar
DELAY_THROTTLE_SEG     = 300    # 5 min si crashea demasiado rápido
BOT_SCRIPT             = "bot_binance.py"


class BotWatchdog:
    def __init__(self):
        self.restart_times  = deque()
        self.total_reinicios = 0
        self.proceso        = None

    def run(self):
        logger.info("=" * 55)
        logger.info("  WATCHDOG 24/7 — Bot Binance IA")
        logger.info("=" * 55)
        self._enviar_telegram("🛡️ *Watchdog 24/7 activado*\nBot Binance IA bajo supervisión continua.")

        while True:
            try:
                logger.info(f"▶️  Iniciando {BOT_SCRIPT} (reinicio #{self.total_reinicios + 1})")
                self.proceso = self._iniciar_bot()

                # Esperar a que el bot termine/crashee
                self.proceso.wait()
                exit_code = self.proceso.returncode

                if exit_code == 0:
                    logger.info("✅ Bot terminó normalmente (exit 0). Watchdog cierra.")
                    break

                # Crash — calcular si debemos esperar o no
                self.total_reinicios += 1
                ahora = datetime.utcnow()
                self.restart_times.append(ahora)

                # Limpiar reinicios viejos (más de 1 hora)
                cutoff = ahora - timedelta(hours=1)
                while self.restart_times and self.restart_times[0] < cutoff:
                    self.restart_times.popleft()

                crashes_hora = len(self.restart_times)
                logger.warning(f"⚠️  Bot crasheó (exit={exit_code}) | Crashes esta hora: {crashes_hora}/{MAX_REINICIOS_POR_HORA}")

                if crashes_hora >= MAX_REINICIOS_POR_HORA:
                    msg = f"🔴 Bot crasheó {crashes_hora}x en 1h. Pausa de {DELAY_THROTTLE_SEG//60} min antes de reiniciar."
                    logger.error(msg)
                    self._enviar_telegram(msg)
                    time.sleep(DELAY_THROTTLE_SEG)
                else:
                    msg = f"🔄 Bot caído. Reiniciando en {DELAY_REINICIO_SEG}s... (total reinicios: {self.total_reinicios})"
                    logger.info(msg)
                    self._enviar_telegram(msg)
                    time.sleep(DELAY_REINICIO_SEG)

            except KeyboardInterrupt:
                logger.info("🛑 Watchdog detenido por usuario (Ctrl+C)")
                self._matar_bot()
                self._enviar_telegram("🔴 Watchdog detenido manualmente")
                break
            except Exception as e:
                logger.error(f"❌ Error crítico en watchdog: {e}")
                time.sleep(30)

    def _iniciar_bot(self) -> subprocess.Popen:
        """Inicia el bot como subproceso."""
        return subprocess.Popen(
            [sys.executable, BOT_SCRIPT],
            stdout=sys.stdout,   # Mostrar output del bot en consola
            stderr=sys.stderr,
        )

    def _matar_bot(self):
        if self.proceso and self.proceso.poll() is None:
            self.proceso.terminate()
            logger.info("Proceso bot terminado por watchdog")

    def _enviar_telegram(self, mensaje: str):
        """Intenta enviar notificación Telegram directamente."""
        try:
            import requests
            from dotenv import load_dotenv
            load_dotenv()
            token   = os.getenv("TELEGRAM_TOKEN", "")
            chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
            if token and chat_id:
                requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"},
                    timeout=10,
                )
        except Exception:
            pass


# ─── Punto de entrada ────────────────────────────────────
if __name__ == "__main__":
    if "--once" in sys.argv:
        # Solo ejecutar el bot directamente sin watchdog
        os.execv(sys.executable, [sys.executable, BOT_SCRIPT])
    else:
        watchdog = BotWatchdog()
        watchdog.run()
