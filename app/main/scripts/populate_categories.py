from app import create_app, db
from app.models import Category

app = create_app()
app.app_context().push()

def populate_categories():
    categories = ['Tools', 'Cooking', 'Sports Equipment', 'Games', 'Music', 'Books', 'Electronics', 'Clothing', 'Outdoor', 'Kids', 'Miscellaneous']
    for cat in categories:
        existing = Category.query.filter_by(name=cat).first()
        if not existing:
            new_category = Category(name=cat)
            db.session.add(new_category)
    db.session.commit()
    print("Categories populated successfully.")

if __name__ == "__main__":
    populate_categories()