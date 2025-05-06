from marshmallow import Schema, fields, validate, post_dump

class BookSchema(Schema):
    """Схема для серіалізації/десеріалізації книг"""
    _id = fields.String(dump_only=True)  # Тільки для виводу, не для валідації вхідних даних
    title = fields.String(required=True)
    author = fields.String(required=True)
    year = fields.Integer(validate=validate.Range(min=0, max=2100))
    isbn = fields.String()
    description = fields.String()
    created_at = fields.DateTime(dump_only=True)  # Тільки для виводу
    updated_at = fields.DateTime(allow_none=True, dump_only=True)  # Може бути None, тільки для виводу
    
    class Meta:
        # Включаємо всі поля за замовчуванням
        ordered = True  # Зберігаємо порядок полів