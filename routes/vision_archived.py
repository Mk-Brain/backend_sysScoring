"""
Code archivé pour détection de visage et décodage de QR code
À déplacer dans les routes principales quand prêt à être utilisé
"""

# import cv2
# import numpy as np
# from pyzbar.pyzbar import decode

# Chemins vers les fichiers du modèle pré-entraîné
# modelFile = "res10_300x300_ssd_iter_140000_fp16.caffemodel"
# configFile = "deploy.prototxt"
# net = cv2.dnn.readNetFromCaffe(configFile, modelFile)

'''@app.get('/take_picture')
def take_picture():
    # Démarrer le flux vidéo de la caméra
    check = False
    cap = cv2.VideoCapture(0)

    while True:
        # Lire une frame de la vidéo
        ret, frame = cap.read()
        
        # S'assurer que la frame a été lue correctement
        if not ret:
            break

        # Convertir la frame en blob pour le passer au modèle de détection
        #extraire le hauteur et la largeur
        (h, w) = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(
                frame, 
                (300, 300)
            ), 
            1.0, 
            (300, 300), 
            (104.0, 177.0, 123.0)
        )

        # Passer le blob au réseau et obtenir les détections
        net.setInput(blob)
        detections = net.forward()

        face = []
        # Boucle sur les détections
        for i in range(0, detections.shape[2]):
            confidence = detections[0, 0, i, 2]

            if confidence > 0.5:
                check = True
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                (startX, startY, endX, endY) = box.astype("int")

                # Dessiner la boîte englobante avec la probabilité
                text = "{:.2f}%".format(confidence * 100)
                y = startY - 10 if startY - 10 > 10 else startY + 10
                cv2.rectangle(frame, (startX, startY), (endX, endY),
                            (0, 255, 0), 2)
                cv2.putText(frame, text, (startX, y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 2)
                
                face = frame[startY:startX + 1, endY:endX + 1]
                
                

        # Afficher la frame avec les détections
        #cv2.imshow("Frame", frame)
        #print(face)
        cv2.imwrite("visage.jpg", face)
        # Sortir de la boucle si on appuie sur 'q'
        #if cv2.waitKey(1) & 0xFF == ord('q'):
        break

    # Libérer le flux vidéo et fermer les fenêtres
    cap.release()
    cv2.destroyAllWindows()
    return {"flag": check}


@app.get('/decode_qr')
def decode_qr():
    webcam = cv2.VideoCapture(0)
    content = None
    # on créé une boucle
    while(True):
        #on recupere frame par frame
        ret, frame = webcam.read()
        decoded = decode(frame)
    
        if not decoded:
            print("Aucun code détecté.")
        else:  
            for obj in decoded:
                x, y, w, h = obj.rect
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                content = obj.data.decode("utf-8", errors="replace")
                print("Contenu :", content)
        # on affiche le frame
        cv2.imshow('frame', frame)
        #on dit au logiciel d'attendre que la touche "q" soit pressée pour arrêter
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    webcam.release()
    cv2.destroyAllWindows()
    return {'contenus':content}
'''
