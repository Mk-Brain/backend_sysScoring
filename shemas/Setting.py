from pydantic import BaseModel


class Setting(BaseModel):
    cle : str
    valeur: str
    description: str
    actif: bool

class SettingResponsModel(BaseModel):
    id: int 
    cle : str
    valeur: str
    description: str
    actif: bool
    #section :str

    class Config:
        from_attributes = True