from marshmallow import Schema, fields

class BookSchema(Schema):
    id = fields.Int(required=True)
    title = fields.Str(required=True)
    author = fields.Str(required=True)
    year = fields.Int(required=True)

book_schema = BookSchema()
