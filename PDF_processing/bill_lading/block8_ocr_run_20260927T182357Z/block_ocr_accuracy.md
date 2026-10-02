# Eight-block OCR accuracy report

- Aggregate field accuracy: **86.08%** (68/79)
- Perfect blocks: **3 of 8**
- Metric: normalized atomic-field recall

| Block | Matched | Expected | Accuracy | Missing items |
|---:|---:|---:|---:|---|
| 1 | 6 | 7 | 85.71% | BL232472785 |
| 2 | 24 | 24 | 100.0% | None |
| 3 | 6 | 6 | 100.0% | None |
| 4 | 1 | 1 | 100.0% | None |
| 5 | 3 | 5 | 60.0% | NO. PKGS; MEASUREMENT |
| 6 | 19 | 23 | 82.61% | HS CODE: 08081080; SET TEMP: +2°C; MRDN7788990; 19,200 |
| 7 | 3 | 6 | 50.0% | FREIGHT & CHARGES; THC; TOTAL NUMBER OF PACKAGES |
| 8 | 6 | 7 | 85.71% | Authorized Signature |

## OCR output by block

### Block 1

Coordinates: `{'x': 67, 'y': 0, 'width': 1999, 'height': 363}`

```text
Mt | MERIDIAN SHIPPING BILL OF LADING
GLOBAL SHIPPING & LOGISTICS B/LNO. 31232472785
SCAC MRDN
```

### Block 2

Coordinates: `{'x': 67, 'y': 363, 'width': 1999, 'height': 899}`

```text
SHIPPER BOOKING REF. SHIPPER'S REF.
FRUTAS DEL SOL S.A. BKG5917532 EXP-35782
Av. de los Incas 456, Buenos Aires, Argentina
TEL: +54 11 4789 1234 | EMAIL: logistica@frutasdelsol.com.ar
PRE-CARRIAGE BY
Oceanic Meridian Lines
CONSIGNEE (NEGOTIABLE ONLY IF CONSIGNED "TO ORDER")
FRESH FRUIT IMPORTERS B.V.
Handelsweg 12, 2988 DB Ridderkerk, Netherlands PLACE OF RECEIPT
TEL: +1 (555) 123-4567 | EMAIL: billing@techcorp.com BUENOS AIRES, ARGENTINA
NOTIFY PARTY (NO RESPONSIBILITY FOR FAILURE TO NOTIFY) DELIVERY AGENT
FRESH FRUIT IMPORTERS B.V. LogiTrans Global
Handelsweg 12, 2988 DB Ridderkerk, Netherlands 88 Harbor Road, Rotterdam, 3011 AA
TEL: +3110 123 4567 | EMAIL: dispatch@logitrans.com Tel: +31 10 123 4567 | dispatch@logitrans.com
```

### Block 3

Coordinates: `{'x': 67, 'y': 1262, 'width': 1999, 'height': 149}`

```text
OCEAN VESSEL / VOYAGE PORT OF LOADING PORT OF DISCHARGE
MERIDIAN LABREA / 124N BUENOS AIRES, ARGENTINA ROTTERDAM, NETHERLANDS
```

### Block 4

Coordinates: `{'x': 67, 'y': 1411, 'width': 1999, 'height': 71}`

```text
PARTICULARS FURNISHED BY SHIPPER - CARRIER NOT RESPONSIBLE
```

### Block 5

Coordinates: `{'x': 67, 'y': 1482, 'width': 1999, 'height': 77}`

```text
CONTAINER NO. / SEAL NO. j No. PKos | DESCRIPTION OF GOODS GROSS WT. | MEASUREMEN
```

### Block 6

Coordinates: `{'x': 67, 'y': 1559, 'width': 1999, 'height': 1185}`

```text
MRDN4455667 20 2@ PALLETS STC: 18,500 28.00
FRESH FRUIT KGS CBM
SEAL: MSK112233
FRESH APPLES
PALLETIZED 20 STOWAGE AT +2.0 DEGREES CELSIUS 19,208 28.00
Packaging: PALLETS KGS CBM
SEAL: MSK445566 SET TEMPS tare
MARKS:
PALLETIZED 20 PALLETS STC:
FRESH FRUIT
FRESH PEARS
STOWAGE AT +1.0 DEGREES CELSIUS
Packaging: PALLETS
HS CODE: 08083090
SET TEMP: +1°C
FREIGHT COLLECT
```

### Block 7

Coordinates: `{'x': 67, 'y': 2744, 'width': 1999, 'height': 256}`

```text
OCEAN FREIGHT COLLECT
~ 40
```

### Block 8

Coordinates: `{'x': 67, 'y': 3000, 'width': 1999, 'height': 341}`

```text
RECEIVED by the Carrier in apparent good order and condition (unless otherwise stated herein) the total number or PLACE OF ISSUE DATE OF ISSUE
quantity of Containers or other packages or units indicated in the box entitled “Total Number of Packages” for
carriage subject to all the terms and conditions hereof from the Place of Receipt or Port of Loading to the Port of
Discharge or Place of Delivery, whichever is applicable. Antwerp 2026-03-1 3
IN ACCEPTING THIS BILL OF LADING THE MERCHANT EXPRESSLY ACCEPTS AND AGREES TO ALL THE TERMS AND
CONDITIONS, WHETHER PRINTED, STAMPED OR OTHERWISE INCORPORATED ON THIS SIDE AND ON THE REVERSE
SIDE OF THIS BILL OF LADING AND THE TERMS AND CONDITIONS OF THE CARRIER'S APPLICABLE TARIFF AS IF
THEY WERE ALL SIGNED BY THE MERCHANT.
SIGNED FOR THE CARRIER
e e
NUMBER OF ORIGINAL B/L'S: THREE (3) / \uthorized Sig natu re
```

