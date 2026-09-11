# OCR Exceptions

Values below were not readable or did not validate against the matching 
synthetic source record. Structured JSON retains the OCR value; the 
suggestion is not silently substituted.

| File | Column | OCR value | Suggested valid value |
|---|---|---|---|
| CLM-100000.png | 1a insured ID | RAGBREDOO | Gy001000 |
| CLM-100000.png | 32 service facility | Northgate Family Medicine<br>75 River Ra, Bethesda, MD 20817 | Northgate Family Medicine<br>75 River Rd, Bethesda, MD 20817 |
| CLM-100001.png | 1a insured ID | APORD17 | Gy001017 |
| CLM-100001.png | 32 service facility | Capital Physician Group<br>£00 K St NW, Washington, DC 20001 | Capital Physician Group<br>800 K St NW, Washington, DC 20001 |
| CLM-100001.png | 24D CPT/HCPCS line B | 46830 | 76830 |
| CLM-100002.png | 1a insured ID | RIGORDS4 | Gy001034 |
| CLM-100002.png | 21 diagnosis ICD-10 | A:223 | A: Z23 |
| CLM-100002.png | 32 service facility | Midwest Cardiology Clinic<br>901 Grand Bivd, Kansas City, MO 64106 | Midwest Cardiology Clinic<br>901 Grand Blvd, Kansas City, MO 64106 |
| CLM-100003.png | 1a insured ID | RIPOREDS1 | Gy001051 |
| CLM-100004.png | 1a insured ID | RAGORDSS | Gy001068 |
| CLM-100004.png | 32 service facility | Northgate Family Medicine<br>75 River Ra, Bethesda, MD 20817 | Northgate Family Medicine<br>75 River Rd, Bethesda, MD 20817 |
| CLM-100004.png | 33 billing provider and NPI | Northgate Family Medicine<br>NPI: 1876543200 | Northgate Family Medicine<br>NPI: 1876543290 |
| CLM-100005.png | 1a insured ID | RIGORRDSS | Gy001085 |
| CLM-100005.png | 32 service facility | St. Mary's Medical Center<br>300 N ‘st Ave, Kansas City, MO 64101 | St. Mary's Medical Center<br>300 N 1st Ave, Kansas City, MO 64101 |
| CLM-100005.png | 33 billing provider and NPI | St. Mary's Medical Center<br>NPI: 1432560871 | St. Mary's Medical Center<br>NPI: 1432569871 |
| CLM-100005.png | 24D CPT/HCPCS line A | DO150 | D0150 |
| CLM-100006.png | 1a insured ID | RAGOREO2 | Gy001102 |
| CLM-100006.png | 32 service facility | Northgate Family Medicine<br>75 River Ra, Bethesda, MD 20817 | Northgate Family Medicine<br>75 River Rd, Bethesda, MD 20817 |
| CLM-100006.png | 33 billing provider and NPI | Northgate Family Medicine<br>NPI: 1876543200 | Northgate Family Medicine<br>NPI: 1876543290 |
| CLM-100006.png | 24D CPT/HCPCS line A | DO150 | D0150 |
| CLM-100007.png | 1a insured ID | RIPORE19 | Gy001119 |
| CLM-100007.png | 21 diagnosis ICD-10 | A:110 | A: I10 |
| CLM-100007.png | 32 service facility | Northgate Family Medicine<br>75 River Ra, Bethesda, MD 20817 | Northgate Family Medicine<br>75 River Rd, Bethesda, MD 20817 |
| CLM-100008.png | 1a insured ID | RIGOREL36 | Gy001136 |
| CLM-100008.png | 5 patient address | 5623 Pine Blvd, Rockville, ¥A 20001 | 5623 Pine Blvd, Rockville, VA 20001 |
| CLM-100008.png | 7 insured address | 5623 Pine Blvd, Rockville, ¥A 20001 | 5623 Pine Blvd, Rockville, VA 20001 |
| CLM-100008.png | 32 service facility | Fairfax Family Practice<br>56 Madison St, Faifax, VA 22030 | Fairfax Family Practice<br>55 Madison St, Fairfax, VA 22030 |
| CLM-100009.png | 1a insured ID | RAGORESS | Gy001153 |
| CLM-100009.png | 32 service facility | Northgate Family Medicine<br>75 River Ra, Bethesda, MD 20817 | Northgate Family Medicine<br>75 River Rd, Bethesda, MD 20817 |
| CLM-100009.png | 24D CPT/HCPCS line A | DO150 | D0150 |
| CLM-100010.png | 1a insured ID | RIPORE7O | Gy001170 |
| CLM-100010.png | 3 birth date | 122976 | 12/12/1976 |
| CLM-100010.png | 32 service facility | Fairfax Family Practice<br>56 Madison St, Faifax, VA 22030 | Fairfax Family Practice<br>55 Madison St, Fairfax, VA 22030 |
| CLM-100010.png | 33 billing provider and NPI | Fairfax Family Practice<br>NPI: 1432560871 | Fairfax Family Practice<br>NPI: 1432569871 |
| CLM-100011.png | 1a insured ID | RIPORES7 | Gy001187 |
| CLM-100011.png | 32 service facility | St. Mary's Medical Center<br>300 N ‘st Ave, Kansas City, MO 64101 | St. Mary's Medical Center<br>300 N 1st Ave, Kansas City, MO 64101 |
| CLM-100012.png | 1a insured ID | RIGORER04 | Gy001204 |
| CLM-100012.png | 5 patient address | #117 Oak Ave, Arlington, DC 20814 | 7117 Oak Ave, Arlington, DC 20814 |
| CLM-100012.png | 7 insured address | #117 Oak Ave, Arlington, DC 20814 | 7117 Oak Ave, Arlington, DC 20814 |
| CLM-100012.png | 32 service facility | Fairfax Family Practice<br>56 Madison St, Faifax, VA 22030 | Fairfax Family Practice<br>55 Madison St, Fairfax, VA 22030 |
| CLM-100013.png | 1a insured ID | RIGOREZ1 | Gy001221 |
| CLM-100013.png | 5 patient address | #221 Oak Ln, Arlington, MD 20001 | 7221 Oak Ln, Arlington, MD 20001 |
| CLM-100013.png | 7 insured address | #221 Oak Ln, Arlington, MD 20001 | 7221 Oak Ln, Arlington, MD 20001 |
| CLM-100013.png | 24D CPT/HCPCS line B | 44178 | 74178 |
| CLM-100014.png | 1a insured ID | RIGOREZ38 | Gy001238 |
| CLM-100014.png | 32 service facility | r= Orthopedic Associates<br>1200 Duke St, Alexandria, VA 22314 | Apex Orthopedic Associates<br>1200 Duke St, Alexandria, VA 22314 |
| CLM-100014.png | 33 billing provider and NPI | r= Orthopedic Associates<br>NPI: 1432560871 | Apex Orthopedic Associates<br>NPI: 1432569871 |
| CLM-100015.png | 1a insured ID | RAGORRSS | Gy001255 |
| CLM-100015.png | 32 service facility | Midwest Cardiology Clinic<br>901 Grand Bivd, Kansas City, MO 64106 | Midwest Cardiology Clinic<br>901 Grand Blvd, Kansas City, MO 64106 |
| CLM-100016.png | 1a insured ID | RIPORET2 | Gy001272 |
| CLM-100016.png | 21 diagnosis ICD-10 | A:223 | A: Z23 |
| CLM-100017.png | 1a insured ID | RPORR8S | Gy001289 |
| CLM-100018.png | 1a insured ID | RIGOREIOG | Gy001306 |
| CLM-100018.png | 32 service facility | Capital Physician Group<br>£00 K St NW, Washington, DC 20001 | Capital Physician Group<br>800 K St NW, Washington, DC 20001 |
| CLM-100019.png | 1a insured ID | BPOEB23 | Gy001323 |
| CLM-100019.png | 32 service facility | Fairfax Family Practice<br>56 Madison St, Faifax, VA 22030 | Fairfax Family Practice<br>55 Madison St, Fairfax, VA 22030 |
| CLM-100019.png | 33 billing provider and NPI | Fairfax Family Practice<br>NPI: 1432560871 | Fairfax Family Practice<br>NPI: 1432569871 |
