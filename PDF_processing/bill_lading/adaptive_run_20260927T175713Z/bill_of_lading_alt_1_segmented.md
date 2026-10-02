# Bill of Lading - segmented OCR

## Document
- Carrier: MERIDIAN SHIPPING - GLOBAL SHIPPING & LOGISTICS
- B/L number: BL232472785
- SCAC: MRDN

## Parties and routing
- Shipper: FRUTAS DEL SOL S.A.; Av. de los Incas 456, Buenos Aires, Argentina; +54 11 4789 1234; logistica@frutasdelsol.com.ar
- Consignee: FRESH FRUIT IMPORTERS B.V.; Handelsweg 12, 2988 DB Ridderkerk, Netherlands; +1 (555) 123-4567; billing@techcorp.com
- Notify party: FRESH FRUIT IMPORTERS B.V.; +31 10 123 4567; dispatch@logitrans.com
- Delivery agent: LogiTrans Global; 88 Harbor Road, Rotterdam, 3011 AA; +31 10 123 4567; dispatch@logitrans.com
- Vessel / voyage: MERIDIAN LABREA / 124N
- Place of receipt and loading: BUENOS AIRES, ARGENTINA
- Port of discharge: ROTTERDAM, NETHERLANDS

## Cargo
| Container | Seal | Marks | Packages | Description | Commodity | Stowage | Packaging | HS code | Set temp | Gross weight | Measurement |
|---|---|---|---:|---|---|---|---|---|---|---:|---:|
| MRDN4455667 | MSK112233 | PALLETIZED | 20 | FRESH FRUIT | FRESH APPLES | +2.0 degrees Celsius | PALLETS | 08081080 | +2 C | 18,500 KGS | 28.00 CBM |
| MRDN7788990 | MSK445566 | PALLETIZED | 20 | FRESH FRUIT | FRESH PEARS | +1.0 degrees Celsius | PALLETS | 08083090 | +1 C | 19,200 KGS | 28.00 CBM |

- Freight: COLLECT
- Charges: OCEAN FREIGHT; THC
- Total packages: 40
- Place/date of issue: Antwerp, 2026-03-13
- Original B/Ls: THREE (3)
- Signature: Authorized Signature

## Human-review flags
- The `MEASUREMENT` heading was not reliably recognized by Tesseract, although both 28.00 CBM values are visible.
- Tight child OCR continued to confuse the decimal zero in `+2.0` and `+1.0`; the values above were transcribed from the clearly legible labeled screenshots.
