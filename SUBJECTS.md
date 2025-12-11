# Subject tagging for recent publications

The `tag_subjects.py` helper applies lightweight keyword heuristics to all journal club entries (currently September–November 2025) and stores subject tags alongside each session.

## Subject heuristics
- **Rhinology & Allergy**: rhino, sinus, nasal/nose, septum, polyps, olfaction/smell, sinonasal, nasopharynx, epistaxis
- **Otology & Neurotology**: cochlea, ear, otic, tympanic/mastoid, ossicular, vestibular, tinnitus, hearing, eustachian
- **Audiology & Hearing Science**: audiology/audiogram, speech perception, listening, hearing aids, cochlear implants
- **Laryngology & Voice**: larynx, vocal cords, voice, phonation, glottis, dysphonia, esophageal topics
- **Airway & Trachea**: airway, trachea, bronchi, intubation/decannulation, stents
- **Sleep Medicine**: sleep, apnea/OSA, hypopnea, CPAP
- **Head & Neck Oncology**: carcinoma, cancer, tumor/neoplasm, sarcoma, oncology, malignant, papilloma
- **Endocrine (Thyroid/Parathyroid)**: thyroid, parathyroid, endocrine
- **Salivary & Oral Cavity**: salivary glands, parotid, submandibular/sublingual, sialo-, oral cavity/tongue/palate/tonsil
- **Facial Plastics & Reconstruction**: facial plastics, reconstruction, rhinoplasty, cleft, aesthetic/cosmetic, flap/graft/scar
- **Skull Base & Cranial**: skull base, cranial/intracranial, cerebrospinal/CSF, pituitary, meningioma
- **Trauma**: trauma, fracture, injury, gunshot, laceration
- **Infectious Disease**: infection, viral, bacterial, fungal, abscess, mycobacterial, sepsis
- **Pediatrics (overlay tag)**: pediatric, child/children, infant, neonate/newborn, adolescent, toddler
- **General ENT/Other**: fallback when no other rule matches

## Running the tagger

```bash
python tag_subjects.py
```

The script rewrites `data/journal_club.json` with updated `subjects` arrays and generates `data/subject_summary.json`, which aggregates subject counts by month.

## Common subjects in the past few months

Based on `data/subject_summary.json`, the most frequent subjects were:
- **September 2025**: Laryngology & Voice (183), General ENT/Other (162), Otology & Neurotology (133), Rhinology & Allergy (98)
- **October 2025**: Laryngology & Voice (211), Otology & Neurotology (127), Rhinology & Allergy (126), General ENT/Other (101)
- **November 2025**: Laryngology & Voice (206), General ENT/Other (157), Otology & Neurotology (129), Rhinology & Allergy (126)
