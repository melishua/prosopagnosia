###############################################################################
#                                                                             #  
#                  Object Detection Source Code For ISee                      #
#                                                                             #  
#-----------------------------------------------------------------------------#
#                                                                             #  
# Description:                                                                #  
# This is a demo of running face recognition on live video from your webcam.  #
# It's a little more complicated than the other example, but it includes some #
# basic performance tweaks to make things run a lot faster:                   #
#   1. Process each video frame at 1/4 resolution (though still display it at #
#      full resolution)                                                       #
#   2. Only detect faces in every other frame of video.                       #
#                                                                             #
# NOTE: This example requires OpenCV (the `cv2` library) to be installed only #
# to read from your webcam. OpenCV is NOT required to use the face_recognition#
# library. It's only required if you want to run this specific demo. If you   #
# have trouble installing it, try any of the other demos that don't require it#
# instead.                                                                    #
###############################################################################

#------------------------------------------------------------------------------
# Libraries Import
#------------------------------------------------------------------------------
import numpy as np
import cv2
import face_recognition
import pyttsx3
import os
import re
import glob
import speech_recognition as sr
from os import path
import math 
from PIL import Image
import sys, select
import shutil

from build_index import build_index
from upload_file import upload_file

#------------------------------------------------------------------------------
# Constants / Global Declaration
#------------------------------------------------------------------------------
# Flag for showing video stream
CV_SHOW_IMAGE_FLAG = True # Keep false until cv2 crash is resolved
# Flag for outputing audio notification
# *TODO*: 
#   The problem crush currently when both video and audio output is enable!!!!
#   So PYTTSX3_OUTPUT_AUDIO is set to !(CV_SHOW_IMAGE_FLAG) for now. The value
#   can be change to specific value when the bug is fixed.
PYTTSX3_OUTPUT_AUDIO = not CV_SHOW_IMAGE_FLAG

SINGLE_DETACTION = True
fixation = (0, 0)

# Default path for adding new annotation file
ANNOTATION_PATH = "./known_annotation"
NUMANNOTATION = 2


# Variables for adding unknown person
UNKNOWN_PERSON_IDX = 1
STARING_THRESHOLD = 1       # Numbers of times seen unknown person to add into contact
KNOWN_FACE_ENCODINGS = []
KNOWN_FACE_NAMES = []

# Seen Counter for Unknown Faces
#   format: {'name':'# seen'}
unknown_ppl_counters = {}

#------------------------------------------------------------------------------
# Environment Setup
#------------------------------------------------------------------------------
# Camera source - Get a reference to webcam #0 (the default one)
video_capture = cv2.VideoCapture(1)

# Audio source - Initiate speech engine
speech_engn = pyttsx3.init()
notify_perct_thresh = 0.3

# speech recognition by obtaining audio from the microphone
#speech_recognizer = sr.Recognizer()

#------------------------------------------------------------------------------
# Function to load Face and annotation records
#------------------------------------------------------------------------------
def LoadFaceAndEncoding(known_ppl_pics):
    # Load a picture of each person and learn how to recognize it.
    for known_person_pic in known_ppl_pics:
        # get this person's name
        image_name = os.path.basename(known_person_pic)
        person_name = os.path.splitext(image_name)[0]

        # get this person's face encoding
        image = face_recognition.load_image_file(known_person_pic)
        face_encoding = face_recognition.face_encodings(image)[0]
        
        #TODO: save this person's name and face encoding in DB!
        # save this person's name and face encoding
        KNOWN_FACE_NAMES.append(person_name)
        KNOWN_FACE_ENCODINGS.append(face_encoding)

        print("I can recognize " + person_name + " now.")

def SetupSpeechEngine():
    rate = speech_engn.getProperty('rate')
    speech_engn.setProperty('rate', rate * 1.225)

#------------------------------------------------------------------------------
# Function to record an unknown person
#------------------------------------------------------------------------------
def RecordUnknownPerson(face_encoding, unknown_id):
    global KNOWN_FACE_ENCODINGS
    global KNOWN_FACE_NAMES
    global UNKNOWN_PERSON_IDX

    # Assign a name to his/her
    person_name = "Unknown_" + str(unknown_id)

    print("in RecordUnknownPerson, person name is: " + person_name)

    # Initialize value in unknown counter
    if person_name in unknown_ppl_counters:
        print("WARNING: unknown person should not be available in unknown_ppl_counters")
    else:
        unknown_ppl_counters[person_name] = 1

    # TODO: save encoding in DB!
    # ie. to save his/her face encoding
    KNOWN_FACE_NAMES.append(person_name)
    KNOWN_FACE_ENCODINGS.append(face_encoding)

    print("Unknown person added, I can recognize " + person_name + " now.")    

    #increment UNKNOWN_PERSON_IDX
    UNKNOWN_PERSON_IDX += 1

    return person_name

def AddUnknownAsContact(unknown_id_name):
    global KNOWN_FACE_NAMES

    # Multiplication of STARING_THRESHOLD to make seen count negative
    # if answer "no" to add contact
    NEG_MULTI_OF_SEEN_THRES = 2

    contact_request = "Would you like to add this person as a contact?"
    print(contact_request)
    answer = GetTextFromAudio(contact_request)

    # Do nothing if user didn't answer the question. Another alternative is to remove the
    # count, but since the voice recongition is flaky right now, let's assume that it is
    # the speach engine that's unable to catch the response.
    if answer is None:
        return

    if IsPositiveResponse(answer):
        name_request = "What is his or her name?"
        name_of_unknown_person = GetTextFromAudio(name_request)

        # update person name
        # TODO: update in DB!
        for idx, known_face_name in enumerate(KNOWN_FACE_NAMES):
            if unknown_id_name in known_face_name:
                print("Update " + unknown_id_name + " to " + name_of_unknown_person)
                KNOWN_FACE_NAMES[idx] = name_of_unknown_person

                # confirm updated contact
                contact_added = GetTextFromAudio(name_of_unknown_person + "is added to your contact list.")
                print("Here is the updated contact list:")

        print(KNOWN_FACE_NAMES)

        # Remove this user from unknown_ppl_counters as name is now added
        del unknown_ppl_counters[unknown_id_name]

    else:
        # Make seen count negative as user answers "no", user will have to see
        # see this person more often for the question to prompt
        unknown_ppl_counters[unknown_id_name] = - NEG_MULTI_OF_SEEN_THRES * STARING_THRESHOLD
        print("No one is added to your contact.")


def slientRecord(face_image, face_encoding, unknown_id):
    # Hard code for now
    cache_directory = "./cache"

    # save image with unknown_id
    #cv2.imshow('image',face_image)
    #cv2.imwrite("{}.jpg".format(unknown_id), face_image)
    pil_image = Image.fromarray(face_image)
    pil_image.save("{}/{}.jpg".format(cache_directory,unknown_id))

    print("capturing unknown contact into database")

    # short recording for 3sec.


#------------------------------------------------------------------------------
# Face Recongition Function
#------------------------------------------------------------------------------
def FaceRecognitionWebcam():
    # TODO: check if database is empty
    # if yes, load Face and annotation records from database and save them
    # if no, then do not need to record these people again
        # load pictures of known people from known_ppl_path
    known_ppl_pics = glob.glob("./face_database/*.jpg")
    LoadFaceAndEncoding(known_ppl_pics)

    # Initialize some variables
    face_locations = []
    face_encodings = []
    face_names = []
    process_this_frame = True
    global STARING_THRESHOLD
    global KNOWN_FACE_NAMES
    global KNOWN_FACE_ENCODINGS
    best_match_index = -1
    last_seen_person = "unknown"

    while True:
        # Grab a single frame of video
        ret, frame = video_capture.read()

        # Resize frame of video to 1/4 size for faster face recognition processing
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)

        # Convert the image from BGR color (which OpenCV uses) to RGB color 
        # (which face_recognition uses)
        rgb_small_frame = small_frame[:, :, ::-1]

        # Mainline Recongition
        #------------------------------------------------------------------------------
        # Only process every other frame of video to save time
        if process_this_frame:
            # Find all the faces and face encodings in the current frame of video
            face_locations = face_recognition.face_locations(rgb_small_frame)

            if SINGLE_DETACTION:
                if len(face_locations) > 1:
                    index = getFaceIndex(face_locations)
                    face_encodings = face_recognition.face_encodings(rgb_small_frame, [face_locations[index]])
                else:
                    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            face_names = []
            for face_encoding in face_encodings:
                # See if the face is a match for the known face(s)
                matches = face_recognition.compare_faces(KNOWN_FACE_ENCODINGS, face_encoding)
                name = "Unknown"

                if True in matches:
                    # If a match was found in KNOWN_FACE_ENCODINGS, just use the first one.
                    # first_match_index = matches.index(True)
                    # name = KNOWN_FACE_NAMES[first_match_index]

                    # Or instead, use the known face with the smallest distance to the new face
                    face_distances = face_recognition.face_distance(KNOWN_FACE_ENCODINGS, face_encoding)
                    best_match_index = np.argmin(face_distances)

                    if matches[best_match_index] and face_distances[best_match_index] < 0.5:
                        name = KNOWN_FACE_NAMES[best_match_index]
                    else:
                        #TODO: we should associate staring counter with each unknown person in DB
                        unknown_name = RecordUnknownPerson(face_encoding, UNKNOWN_PERSON_IDX)

                        print("Recognized new unknown person: {} with counter: {}".format(unknown_name, unknown_ppl_counters[unknown_name]))

                    # It is possible that matched person is actually unknown in database.
                    # Handle this case with special care:
                    #   Count the number of times this unknown person is seen
                    if "unknown" in name.lower() and name in unknown_ppl_counters:
                        # Increment seen count
                        unknown_ppl_counters[name] += 1
                        print("Staring count is: " + str(unknown_ppl_counters[name]))

                        # if you continue to stare at this unknown person
                        # i.e. might be having a conversation with
                        # prompt to add this person as a contact
                        if unknown_ppl_counters[name] > STARING_THRESHOLD:

                            #AddUnknownAsContact(name)
                            top, right, bottom, left = face_locations[0][0], face_locations[0][1], face_locations[0][2], face_locations[0][3]
                            face_img = rgb_small_frame[top:bottom, left:right]
                            print("face_image: {}, dimension: {} {} {} {}".format(face_img, top, right, bottom, left))
                            slientRecord(face_img, face_encoding, name)

                    # Prompt information to user
                    NotifyNameAndInfo(name, best_match_index)

                    # Feature to add new person or annotation
                    # if "unknown" not in name.lower() and name != last_seen_person:
                    #     OptionForNewAnnotation(best_match_index, name)

                    # TODO: option to pull out all of this person's pictures

                    # Update last seen person
                    last_seen_person = name

                face_names.append(name)
                break

        # Display the results
        if CV_SHOW_IMAGE_FLAG:
            for (top, right, bottom, left), name in zip(face_locations, face_names):
                # Scale back up face locations since the frame we detected in was scaled to 1/4 size
                top *= 4
                right *= 4
                bottom *= 4
                left *= 4

                # Draw a box around the face
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)

                # Draw a label with a name below the face
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 0, 255), cv2.FILLED)
                font = cv2.FONT_HERSHEY_DUPLEX
                cv2.putText(frame, name, (left + 6, bottom - 6), font, 1.0, (255, 255, 255), 1)
        
            # Display the resulting image
            cv2.imshow('Video', frame)

            # Hit 'q' on the keyboard to quit!
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        # Update frame control knob
        process_this_frame = not process_this_frame

#return the index of the face that is closest to fixation in face_locations
def getFaceIndex(face_locations):
    fixation_distances = []
    for coordinate in face_locations:
        print(coordinate[0], coordinate[1])
        fixation_distances.append((int(coordinate[0]) - fixation[0])**2 + (int(coordinate[1]) - fixation[1])**2)
    return fixation_distances.index(min(fixation_distances))

#------------------------------------------------------------------------------
# Voice Notification Functions
#------------------------------------------------------------------------------
def VoiceNotification(str_txt):
    speech_engn.say(str_txt)
    speech_engn.runAndWait()

def NotifyNameAndInfo(name, idx):
    notification = ""
    annotations = []

    # Format notification message
    if "Unknown" in name:
        notification = "There is an unknown person in front you."
    else:
        notification = "This is " + name
        annotations = ReadAnnotationFromId(idx)

    # Notify name
    if PYTTSX3_OUTPUT_AUDIO:
        VoiceNotification(notification)
    else:
        print("NOTFIY: {}".format(notification))

    # Notify annotations
    counter = 0
    for a in annotations:
        if PYTTSX3_OUTPUT_AUDIO:
            VoiceNotification(a)
        else:
            print("ANNOTATION: {}".format(a))

        # only read out certain number of annotations
        if counter > NUMANNOTATION:
            break
    print("\n")

#------------------------------------------------------------------------------
# Speech Recognition Functions
#------------------------------------------------------------------------------
def GetTextFromAudio(indicator):
    with sr.Microphone() as source:
        VoiceNotification(indicator)
        audio = speech_recognizer.listen(source,phrase_time_limit=6)

    # recognize speech using Google Speech Recognition
    try:
        # for testing purposes, we're just using the default API key
        # to use another API key, use `r.recognize_google(audio, key="GOOGLE_SPEECH_RECOGNITION_API_KEY")`
        # instead of `r.recognize_google(audio)`
        text = speech_recognizer.recognize_google(audio)
        print("Google Speech Recognition thinks you said " + text)
        return text
    except sr.UnknownValueError:
        print("Google Speech Recognition could not understand audio")
    except sr.RequestError as e:
        print("Could not request results from Google Speech Recognition service; {0}".format(e))
        pass
    except Exception as e:
        print("Other speech recongition error: {0}".format(e))
        raise

#------------------------------------------------------------------------------
# Annotation Related Functions
#------------------------------------------------------------------------------
def ReadAnnotationFromId(idx):
    # Get matching annotation file from database
    af, found = GetAnnotationByFRId(idx)

    if found == False:
        return []

    # Read Annotation File
    f = open(af, "r")

    annotations = f.readlines()

    # close the file after reading the lines.
    f.close()

    return annotations

def AnnotateById(idx, annotations):
    # Get matching annotation file from database
    af, found = GetAnnotationByFRId(idx)

    try:
        f = open(af, "a+")

        # Create new file if annotation not found
        if not found:
            af = ANNOTATION_PATH + "/" + str(idx) + ".txt"
            f = open(af, "w+") 

        # Append new annotation line by line
        for a in annotations:
            if a is not None:
                f.write(a + '\n')

        # close the file after writing the lines.
        f.close()
    except IOError:
        print ("Warning: Unable to open & write annotation record for ID:{}".format(idx))
        pass

def AnnotateByName(name, annotations):
    # Get matching annotation file from database
    af, found = GetAnnotationByName(name)

    try:
        f = open(af, "a+")

        # Create new file if annotation not found
        if not found:
            af = "{}/{}.txt".format(ANNOTATION_PATH, name)
            f = open(af, "w+") 

        # Append new annotation line by line
        if annotations is not None:
            f.write(annotations + '\n')

        # close the file after writing the lines.
        f.close()
    except IOError:
        print ("Warning: Unable to open & write annotation record for ID:{}".format(idx))
        pass

def OptionForNewAnnotation(idx, name):
    """Prompt User to add new annotation if needed"""
    annotation_request = "Would you like to add note for " + name + "?"
    print(annotation_request)
    addFlag = GetTextFromAudio(annotation_request)

    annotations = []

    while IsPositiveResponse(addFlag):
        # Prompt user to input note
        annotate = GetTextFromAudio("Please state your note")

        # Save output to list
        annotations.append(annotate)

        # Continue 
        continue_record_request = "Would you like to add more note?"
        print(continue_record_request)

        # Prompt for more annotation
        addFlag = GetTextFromAudio(continue_record_request)

    # Record annotation if there is any
    if annotations:
        AnnotateById(idx, annotations)

#------------------------------------------------------------------------------
# Database functions
#------------------------------------------------------------------------------

def GetAnnotationByFRId(idx):
    # hardcode for now 
    personal_annotation = ANNOTATION_PATH + "/"+ str(idx) + ".txt"
    if os.path.exists(personal_annotation) == True:
        return (personal_annotation, True)
    else:
        return ('No such file', False)

def GetAnnotationByName(name):
    # hardcode for now 
    personal_annotation = ANNOTATION_PATH + "/"+ str(name) + ".txt"
    if os.path.exists(personal_annotation) == True:
        return (personal_annotation, True)
    else:
        return ('No such file', False)
# def updateAnnotationByFR(name,path):
# def idToName(id):
# def nameToId(name):


#------------------------------------------------------------------------------
# General Utility functions
#------------------------------------------------------------------------------
def IsPositiveResponse(response):
    if response is None:
        return False

    if ( "yes"  in response.lower() or
         "yup"  in response.lower() or
         "yah"  in response.lower() or
         "sure" in response.lower() or
         "ok"   in response.lower() or
         "go ahead" in response.lower() ):
        return True
    else:
        return False


#------------------------------------------------------------------------------
# Add New Contact or Annotation Logic
#------------------------------------------------------------------------------
def TimedInputPrompt(t, q):
    print ("{} seconds time out".format(t))
    print (q)

    i, o, e = select.select( [sys.stdin], [], [], t )

    if i:
        return sys.stdin.readline().strip()
    else:
        return ""

def ConsoleSaveUnknownFaces():
    print("\n\nPlease manage unknown person you have seen today")

    # Loop over unknown faces
    cap_img = glob.glob1('./cache',"*.jpg")
    num_cap_img = len(cap_img)

    if num_cap_img != 0:
        answer = TimedInputPrompt(5, "Would you like to add {} captured unknown people into you contact? [y/n]\n".format(num_cap_img))

        if "y" in answer.lower():
            for im in cap_img:
                im_p = Image.open('./cache/{}'.format(im))
                im_p.show()
                print("Please enter the name for this person if you want to save to contact, else enter nothing")
                name = input()
                if name == '':
                    # remove cache photo
                    os.remove('./cache/{}'.format(im))
                    print("{} removed from cache".format(im))
                else:
                    shutil.move('./cache/{}'.format(im), './face_database/{}.jpg'.format(name))

        # cleanup remaining cache files
        cap_img = glob.glob1('./cache',"*.jpg")
        for f in cap_img:
            os.remove('./cache/{}'.format(f))

    # Wait to ask to add annotation
    flag = True
    ctr = 0
    while flag:
        answer = TimedInputPrompt(5, "\nWould you like to add annotation for people in the contact? [y/n]")
        if "y" in answer.lower():
            kwn_img = glob.glob1('./face_database',"*.jpg")

            print("Please enter name of the contact: ")
            name = input()

            match = [f for f in kwn_img if name.lower() in f.lower()]

            if len(match) == 0:
                print("{} is not found in the contact, please enter another name".format(name))
            elif len(match) == 1:
                print("Please enter annotation for the contact:\n")
                annotation = input()
                base = os.path.basename(match[0])
                fname = os.path.splitext(base)[0]
                AnnotateByName(fname, annotation)
                ctr = 0
            else:
                print("More than one contact is found with this name, please enter the full name:\n{}".format(match))
        else:
            flag = False

        ctr += 1

        if ctr > 3:
            break
    print("\n\nProgram existing now, thanks for using :)")


#------------------------------------------------------------------------------
# Cleanup Functions
#------------------------------------------------------------------------------
def GeneralCleanup():
    # Turn off audio source
    speech_engn.stop()
    # Release handle to the webcam
    video_capture.release()
    cv2.destroyAllWindows()

#------------------------------------------------------------------------------
# Run Program
#------------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        while(True):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((HOST, PORT))
                # s.sendall((b'Hello, world'))
                while(True):
                    data = s.recv(1024)

                    print('Received', repr(data))
                coord = [int(s) for s in str.split() if s.isdigit()] 
                fixation = (coord[0], coord[1])    
    
        SetupSpeechEngine()
        FaceRecognitionWebcam()
        GeneralCleanup()
    except Exception as e:
        raise e
