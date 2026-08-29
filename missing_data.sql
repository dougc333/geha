-- =====================================================================
-- Missing-data detection for resolved GEHA claim forms.
--
-- Finds rows where any required claim field is NULL/empty (i.e. the OCR +
-- vector resolver could not recover it, or it was blank on the form).
-- Stores two metadata columns per row:
--     missing_data = 'Yes' | 'No'
--     missing_fields = comma-separated list of the NULL/empty column names
--
-- Run AFTER load_mysql.py has populated claims_resolved. Run via:
--     mysql --host=127.0.0.1 --port=3306 -uroot -pgeha_root geha_claims < missing_data.sql
-- =====================================================================

-- 0) Make the target table usable with the metadata columns.
--    (Run the CREATE + these columns from load_mysql.py first; this file
--     assumes missing_data / missing_fields already exist. If not, add them
--     with plain ALTER TABLE before running this script:
--        ALTER TABLE claims_resolved ADD COLUMN missing_data VARCHAR(3) DEFAULT 'No';
--        ALTER TABLE claims_resolved ADD COLUMN missing_fields TEXT NULL;
--    )

-- 1) Reset the metadata columns so re-runs are idempotent.
UPDATE claims_resolved SET missing_data = 'No', missing_fields = NULL;

-- 2) The core missing-field detection. We use CONCAT_WS to build a
--    comma-separated list of every required column that is NULL or empty.
--    Required form fields: patient_name, patient_dob, patient_sex, member_id,
--    diagnosis, cpt, pos, dos, charge, auth_number, provider, npi, facility.
--    (source_image, ocr_text, claim_id are key/metadata and excluded.)
UPDATE claims_resolved
SET
    missing_fields = CONCAT_WS(',',
        IF(patient_name IS NULL OR patient_name = '',  'patient_name',  NULL),
        IF(patient_dob  IS NULL OR patient_dob  = '',  'patient_dob',   NULL),
        IF(patient_sex  IS NULL OR patient_sex  = '',  'patient_sex',   NULL),
        IF(member_id    IS NULL OR member_id    = '',  'member_id',     NULL),
        IF(diagnosis    IS NULL OR diagnosis    = '',  'diagnosis',     NULL),
        IF(cpt          IS NULL OR cpt          = '',  'cpt',           NULL),
        IF(pos          IS NULL OR pos          = '',  'pos',           NULL),
        IF(dos          IS NULL OR dos          = '',  'dos',           NULL),
        IF(charge       IS NULL,                       'charge',        NULL),
        IF(auth_number  IS NULL OR auth_number  = '',  'auth_number',   NULL),
        IF(provider     IS NULL OR provider     = '',  'provider',      NULL),
        IF(npi          IS NULL OR npi          = '',  'npi',           NULL),
        IF(facility     IS NULL OR facility     = '',  'facility',      NULL)
    );

-- 3) Set the missing_data flag based on whether any field was missing.
UPDATE claims_resolved
SET missing_data = IF(missing_fields IS NULL OR missing_fields = '', 'No', 'Yes');

-- 4) Report rows that have missing data (with the CSV field list).
SELECT claim_id, source_image, missing_data, missing_fields
FROM claims_resolved
WHERE missing_data = 'Yes'
ORDER BY claim_id;

-- 5) Summary: how many claims have complete vs. missing data.
SELECT missing_data, COUNT(*) AS claim_count
FROM claims_resolved
GROUP BY missing_data;
