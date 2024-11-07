from app import create_app, db
from app.models import ItemCategory

def init_db():
    app = create_app()
    with app.app_context():
        db.create_all()
        
        # Add default categories
        categories = [
            'Tools', 'Sports Equipment', 'Electronics', 
            'Books', 'Kitchen', 'Garden', 'Games'
        ]
        
        for cat_name in categories:
            if not ItemCategory.query.filter_by(name=cat_name).first():
                cat = ItemCategory(name=cat_name)
                db.session.add(cat)
        
        db.session.commit()

if __name__ == '__main__':
    init_db()