#!/usr/bin/env python3
# escaner.py
# Lector USB (emula teclado). Lee líneas desde stdin, valida contra API de QRs y guarda/envía la asistencia.

import sys
import os
import time
import json
import hashlib
import requests
import datetime
import sqlite3
import threading
from pathlib import Path

API_QR_BASE = os.environ.get("SSR_QR_API", "http://localhost:5000")
ATTENDANCE_API = os.environ.get("SSR_ATTENDANCE_API")
CACHE_REFRESH_SECONDS = int(os.environ.get("SSR_CACHE_REFRESH", "300"))
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = OUTPUT_DIR / "scanner.db"
UNSENT_RETRY_INTERVAL = int(os.environ.get("SSR_RETRY_SECONDS", "30"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_db_conn():
	return sqlite3.connect(DB_PATH, timeout=10)


def init_db():
	conn = get_db_conn()
	c = conn.cursor()
	c.execute(
		"""
		CREATE TABLE IF NOT EXISTS scans (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			date TEXT,
			timestamp TEXT,
			qr_hash TEXT,
			nombre TEXT,
			payload TEXT,
			scanner TEXT,
			sent INTEGER DEFAULT 0
		)
		"""
	)
	c.execute("CREATE INDEX IF NOT EXISTS idx_sent ON scans(sent)")
	conn.commit()
	conn.close()


def sha256_of_json(obj):
	s = json.dumps(obj, ensure_ascii=False)
	return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_qr_index():
	try:
		r = requests.get(f"{API_QR_BASE}/api/alumnos", timeout=5)
		r.raise_for_status()
		data = r.json()
		mapping = {item["hash"]: item["nombre"] for item in data.get("alumnos", [])}
		print(f"[info] Cargado índice de {len(mapping)} QRs desde {API_QR_BASE}")
		return mapping
	except Exception as e:
		print(f"[warn] No se pudo cargar índice de QRs: {e}")
		return {}


def insert_scan(row):
	conn = get_db_conn()
	c = conn.cursor()
	c.execute(
		"INSERT INTO scans(date,timestamp,qr_hash,nombre,payload,scanner,sent) VALUES (?,?,?,?,?,?,?)",
		(row["date"], row["timestamp"], row["qr_hash"], row["nombre"], row["payload"], row["scanner"], 0),
	)
	conn.commit()
	last = c.lastrowid
	conn.close()
	return last


def mark_sent(scan_id):
	conn = get_db_conn()
	c = conn.cursor()
	c.execute("UPDATE scans SET sent=1 WHERE id=?", (scan_id,))
	conn.commit()
	conn.close()


def get_unsent(limit=50):
	conn = get_db_conn()
	c = conn.cursor()
	rows = c.execute("SELECT id,date,timestamp,qr_hash,payload,scanner FROM scans WHERE sent=0 ORDER BY id LIMIT ?", (limit,)).fetchall()
	conn.close()
	return rows


def post_attendance(payload):
	if not ATTENDANCE_API:
		return None
	try:
		r = requests.post(ATTENDANCE_API, json=payload, timeout=6)
		return r
	except Exception as e:
		print(f"[error] Envío a attendance API falló: {e}")
		return None


def retry_loop(stop_event):
	while not stop_event.is_set():
		try:
			unsent = get_unsent(limit=100)
			if unsent:
				print(f"[retry] Reintentando {len(unsent)} envíos...")
			for row in unsent:
				scan_id, date, ts, hashv, payload_txt, scanner = row
				payload = {"hash": hashv, "scanner": scanner}
				if payload_txt:
					try:
						payload["payload"] = json.loads(payload_txt)
					except Exception:
						payload["payload"] = payload_txt
				resp = post_attendance(payload)
				if resp is not None and 200 <= resp.status_code < 300:
					mark_sent(scan_id)
					print(f"[retry] Envío OK id={scan_id} status={resp.status_code}")
				else:
					print(f"[retry] Falló id={scan_id} status={getattr(resp, 'status_code', None)}")
					# si falla, dejamos para reintentar luego
			time.sleep(UNSENT_RETRY_INTERVAL)
		except Exception as e:
			print(f"[retry] Excepción en retry loop: {e}")
			time.sleep(UNSENT_RETRY_INTERVAL)


def main():
	init_db()
	qr_index = load_qr_index()
	last_cache = time.time()
	recent = set()
	dup_ttl = 5

	stop_event = threading.Event()
	t = threading.Thread(target=retry_loop, args=(stop_event,), daemon=True)
	t.start()

	print("Escuchando scanner (presiona Ctrl+C para salir)...")
	try:
		while True:
			line = sys.stdin.readline()
			if not line:
				time.sleep(0.1)
				continue
			data = line.strip()
			if not data:
				continue

			if time.time() - last_cache > CACHE_REFRESH_SECONDS:
				qr_index = load_qr_index()
				last_cache = time.time()

			payload_obj = None
			hashv = None
			if data.startswith("{") or data.startswith("["):
				try:
					payload_obj = json.loads(data)
					hashv = sha256_of_json(payload_obj)
				except Exception:
					hashv = data
			else:
				try:
					payload_obj = json.loads(data)
					hashv = sha256_of_json(payload_obj)
				except Exception:
					hashv = data

			now = datetime.datetime.utcnow().isoformat()
			date_str = datetime.date.today().isoformat()

			key_recent = (hashv, date_str)
			if key_recent in recent:
				print(f"[dup] Duplicado reciente: {hashv}")
				continue
			recent.add(key_recent)

			def cleanup():
				time.sleep(dup_ttl)
				try:
					recent.discard(key_recent)
				except Exception:
					pass

			threading.Thread(target=cleanup, daemon=True).start()

			nombre = qr_index.get(hashv)
			if nombre:
				print(f"[ok] QR válido: {nombre} (hash {hashv})")
			else:
				try:
					r = requests.get(f"{API_QR_BASE}/api/qr/imagen/{hashv}", timeout=4, stream=True)
					if r.status_code == 200:
						nombre = "(QR encontrado por imagen)"
						print(f"[ok] QR válido (imagen) hash {hashv}")
						qr_index = load_qr_index()
						last_cache = time.time()
					else:
						print(f"[fail] QR no encontrado: {hashv} (status {r.status_code})")
				except Exception as e:
					print(f"[warn] Error consultando API de QRs: {e}")

			row = {
				"date": date_str,
				"timestamp": now,
				"qr_hash": hashv,
				"nombre": nombre or "",
				"payload": json.dumps(payload_obj, ensure_ascii=False) if payload_obj else "",
				"scanner": os.uname().nodename,
			}

			scan_id = insert_scan(row)
			print(f"[saved] scan id={scan_id} hash={hashv}")

			# intentar enviar inmediatamente
			if ATTENDANCE_API:
				payload = {"hash": hashv, "scanner": row["scanner"]}
				if payload_obj:
					payload["payload"] = payload_obj
				resp = post_attendance(payload)
				if resp is not None and 200 <= resp.status_code < 300:
					mark_sent(scan_id)
					print(f"[send] Envío OK id={scan_id} status={resp.status_code}")
				else:
					print(f"[send] Envío pendiente id={scan_id} status={getattr(resp, 'status_code', None)}")

	except KeyboardInterrupt:
		print("Saliendo...")
	finally:
		stop_event.set()


if __name__ == "__main__":
	main()
