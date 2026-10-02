# Bill of Lading - one-shot OCR

- Engine: Tesseract 5.5.1, PSM 6
- Localized errors after visual comparison: **10**

```text
| wi | GLOBAL SHIPPING & LOGISTICS TT
B/L NO. BL232472785
SCAC MRDN
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
TEL: +3110 123 4567 | EMAIL: dispatch@logitrans.com Tel: +3110 123 4567 | dispatch@logitrans.com
OCEAN VESSEL / VOYAGE PORT OF LOADING PORT OF DISCHARGE
MERIDIAN LABREA | 124N BUENOS AIRES, ARGENTINA ROTTERDAM, NETHERLANDS
PARTICULARS FURNISHED BY SHIPPER - CARRIER NOT RESPONSIBLE
[cowramenno./seaino. | wo.pxcs | vescmierioworcooos =| ences wr. | mensuneneny
MRDN4455667 20 20 PALLETS STC: 18,500 28.00
FRESH FRUIT KGS CBM
SEAL: MSK112233
FRESH APPLES
MARKS: 20
PALLETIZED STOWAGE AT +2.@0 DEGREES CELSIUS 19,200 28.00
Packaging: PALLETS KGS CBM
HS CODE: 08081080
MRDN7788990
SET TEMP: +2°C
SEAL: MSK445566
MARKS:
PALLETIZED 20 PALLETS STC:
FRESH FRUIT
FRESH PEARS
STOWAGE AT +1.@ DEGREES CELSIUS
Packaging: PALLETS
HS CODE: 08083090
SET TEMP: +1°C
OCEAN FREIGHT COLLECT
THC O
RECEIVED by the Carrier in apparent good order and condition (unless otherwise stated herein) the total number or PLACE OF ISSUE DATE OF ISSUE
quantity of Containers or other packages or units indicated in the box entitled "Total Number of Packages” for
i Hl d h f fi he Pl if Ri i Pe yf Li it he P. f
IN ACCEPTING THIS BILL OF LADING THE MERCHANT EXPRESSLY ACCEPTS AND AGREES TO ALL THE TERMS AND
CONDITIONS, WHETHER PRINTED, STAMPED OR OTHERWISE INCORPORATED ON THIS SIDE AND ON THE REVERSE
SIDE OF THIS BILL OF LADING AND THE TERMS AND CONDITIONS OF THE CARRIER'S APPLICABLE TARIFF AS IF
THEY WERE ALL SIGNED BY THE MERCHANT. SIGNED FOR THE CARRIER
NUMBER OF ORIGINAL B/L'S: THREE (3) Authorized Sig natu re
FRUTAS DEL SOL S.A. + +54 11 4789 1234 - logistica@frutasdelsol.com.ar
```

## Errors

- document title/logo line is garbled
- notify and delivery-agent phone spacing is collapsed
- cargo table headers are garbled
- cargo rows are read out of column order
- +2.0 is read as +2.@0
- +1.0 is read as +1.@
- total package value 40 is omitted
- place and date of issue values are omitted
- one legal-text line is garbled
- signature text is split
