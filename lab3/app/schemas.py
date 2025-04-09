from marshmallow import Schema, fields, validate

class BookSchema(Schema):
    id = fields.Int(dump_only=True)  # тільки для виводу, не для створення
    title = fields.Str(required=True, validate=validate.Length(min=1))
    author = fields.Str(required=True, validate=validate.Length(min=1))
    year = fields.Int(required=True, validate=[
        validate.Range(min=0, max=2100, error="Рік має бути між 0 та 2100")
    ])

book_schema = BookSchema()
books_schema = BookSchema(many=True)