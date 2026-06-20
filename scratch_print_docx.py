import docx

doc = docx.Document("temp_test/output.docx")
print("=== Redacted DOCX Paragraphs ===")
for p in doc.paragraphs:
    print(repr(p.text))
