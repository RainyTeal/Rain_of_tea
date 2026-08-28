from sqlmodel import SQLModel,select,Session,create_engine,Field
class User(SQLModel,table=True):
    id:int=Field(default=None,primary_key=True)
    username:str=Field(index=True)
    password:str
engine = create_engine("sqlite:///database.db")
SQLModel.metadata.create_all(engine)
while 1:
    with Session(engine) as session:
        op=input()
        if(op=="list"):
            print(session.exec(select(ai_content)).all())
        if(op=="select" or op=="sel"):
            name=input()
            print(session.exec(select(ai_content).where(ai_content.user_uuid==name)).all())
        if(op=="delete" or op=="remove"):
            name=input()
            user=session.exec(select(ai_content).where(ai_content.user_uuid==name)).first()
            if not user:
                print("未找到")
                continue
            session.delete(user)
            session.commit()
