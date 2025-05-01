from app.models.documents import Collection

def get_or_create_collection(session, name: str = "default", source_type="manual"):
    normalized_name = name.strip().lower()
    collection = session.query(Collection).filter_by(name=normalized_name).first()
    if not collection:
        collection = Collection(name=name, source_type=source_type)
        session.add(collection)
        session.commit()
    return collection