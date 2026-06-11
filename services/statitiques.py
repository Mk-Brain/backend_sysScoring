from datetime import date, datetime, time


from sqlalchemy.orm import Session

from models.employe import Employe
from models.pointages import Pointage, ScoringState
from models.statistique import  Statistique

DUREE_NORMALE = 8 * 60

def init_stats_month(db,employe_id, date_debut,date_fin):
        stat = Statistique(
            type_periode="month",
            date_debut=date_debut,
            date_fin=date_fin,
            nb_presence=0,
            nb_absence=0,
            nb_retard=0,
            total_minutes_travail=0,
            total_minutes_sup=0,
            total_minutes_absence=0,
            id_user=employe_id
        )

        db.add(stat)



def init_stats_year(db,employe_id,date_debut,date_fin):
        stat = Statistique(
            type_periode="year",
            date_debut=date_debut,
            date_fin=date_fin,
            nb_presence=0,
            nb_absence=0,
            nb_retard=0,
            total_minutes_travail=0,
            total_minutes_sup=0,
            total_minutes_absence=0,
            id_user=employe_id
        )

        db.add(stat)



def init_stats_week(db,employe_id,date_debut,date_fin):
        stat = Statistique(
            type_periode="week",
            date_debut=date_debut,
            date_fin=date_fin,
            nb_presence=0,
            nb_absence=0,
            nb_retard=0,
            total_minutes_travail=0,
            total_minutes_sup=0,
            total_minutes_absence=0,
            id_user=employe_id
        )

        db.add(stat)


def recuperer_statistique_active(
    db,
    employe_id,
    type_periode,
    date_jour
):

    return (
        db.query(Statistique)
        .filter(
            Statistique.id_user == employe_id,
            Statistique.type_periode == type_periode,
            Statistique.date_debut <= date_jour,
            Statistique.date_fin >= date_jour
        )
        .first()
    )


def mettre_a_jour_statistique(
    statistique,
    pointage,
    minutes_travail
):

    if pointage.status == ScoringState.PRESENT:

        statistique.nb_presence += 1

    elif pointage.status == ScoringState.ABSENT:

        statistique.nb_absence += 1

        statistique.total_minutes_absence += (
            DUREE_NORMALE
        )

    elif pointage.status == ScoringState.RETARD_PRESENT:

        statistique.nb_presence += 1
        statistique.nb_retard += 1

    statistique.total_minutes_travail += (
        minutes_travail
    )

    if minutes_travail > DUREE_NORMALE:

        statistique.total_minutes_sup += (
            minutes_travail - DUREE_NORMALE
        )

def mettre_a_jour_toutes_les_statistiques(
    db,
    pointage,
    minutes_travail
):

    types = [
        "week",
        "month",
        "year"
    ]
    #appliquer la mise à jour pour chaque periode
    for type_periode in types:

        stat = recuperer_statistique_active(
            db,
            pointage.id_user,
            type_periode,
            pointage.date_day
        )

        if stat:

            mettre_a_jour_statistique(
                stat,
                pointage,
                minutes_travail
            )

    db.commit()




def traitement_statistiques_journalieres(db: Session):

    aujourd_hui = date.today()

    employes = db.query(Employe).all()

    for employe in employes:
        #recuperer le pointage et mettre à jour ses statistiques
        pointage = (
            db.query(Pointage)
            .filter(
                Pointage.id_user == employe.id,
                Pointage.date_day == aujourd_hui
            )
            .first()
        )

        if not pointage:
            break

        minutes_travail = 0

        if pointage.heure_arrive is not None and pointage.heure_depart is not None:
            minutes_travail = calculer_minutes_travail(
                pointage.heure_arrive,
                pointage.heure_depart
            )

            mettre_a_jour_toutes_les_statistiques(
                db,
                pointage,
                minutes_travail
            )

    db.commit()


def calculer_minutes_travail(heure_arrive: time, heure_depart: time) -> int:

    date_fictive = date(2000, 1, 1)
    dt_arrive = datetime.combine(date_fictive, heure_arrive)
    dt_depart = datetime.combine(date_fictive, heure_depart)

    difference = dt_depart - dt_arrive

    # Convertit la différence en minutes
    minutes = int(difference.total_seconds() / 60)

    return minutes