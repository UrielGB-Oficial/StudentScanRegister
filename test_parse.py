import csv
with open('generador_qr/src/data/input/CRN207735.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    print(f"Campos: {reader.fieldnames}")
    for i, row in enumerate(reader):
        print(f"Fila {i}: {row}")
        if i >= 2: break
