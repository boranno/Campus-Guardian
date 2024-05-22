import cv2
import face_recognition
import os
from datetime import datetime
import pandas as pd
import pyttsx3
import shutil
import time
import getpass
import bcrypt

# Global variables to store intruder face data and camera assignments
intruder_data = []
camera_roles = {"entry gate": [], "exit gate": [], "restricted area": [], "classroom": [], "ordinary camera": []}
role_map = {1: "entry gate", 2: "exit gate", 3: "restricted area", 4: "classroom", 5: "ordinary camera"}

# Access control for restricted areas
restricted_area_access = {
    "student": False,
    "admin": False,
    "teacher": False,
    "guest": False
}

# Initialize the pyttsx3 engine
engine = pyttsx3.init()



art = '''
     ______     ___      .___  ___. .______    __    __       _______.                   
    /      |   /   \     |   \/   | |   _  \  |  |  |  |     /       |                   
   |  ,----'  /  ^  \    |  \  /  | |  |_)  | |  |  |  |    |   (----`                   
   |  |      /  /_\  \   |  |\/|  | |   ___/  |  |  |  |     \   \                       
   |  `----./  _____  \  |  |  |  | |  |      |  `--'  | .----)   |                      
    \______/__/     \__\ |__|  |__| | _|       \______/  |_______/                       
                                                                                          
     _______  __    __       ___      .______       _______   __       ___      .__   __.
    /  _____||  |  |  |     /   \     |   _  \     |       \ |  |     /   \     |  \ |  |
   |  |  __  |  |  |  |    /  ^  \    |  |_)  |    |  .--.  ||  |    /  ^  \    |   \|  |
   |  | |_ | |  |  |  |   /  /_\  \   |      /     |  |  |  ||  |   /  /_\  \   |  . `  |
   |  |__| | |  `--'  |  /  _____  \  |  |\  \----.|  '--'  ||  |  /  _____  \  |  |\   |
    \______|  \______/  /__/     \__\ | _| `._____||_______/ |__| /__/     \__\ |__| \__|
    '''


def get_terminal_size():
    size = shutil.get_terminal_size((80, 20))
    return size.columns, size.lines

def print_centered_text(text):
    columns, rows = get_terminal_size()
    lines = text.splitlines()
    
    # Calculate the vertical padding to center the text vertically
    vertical_padding = (rows - len(lines)) // 2
    
    # Print vertical padding (blank lines)
   # for _ in range(vertical_padding):
      #  print()
    
    # Print each line with horizontal padding
    for line in lines:
        horizontal_padding = (columns - len(line)) // 2
        print(' ' * horizontal_padding + line)
    




# Function to play a warning message
def play_warning(message):
    engine.setProperty('rate', 150)  # Speed percent (can go over 100)
    engine.setProperty('volume', 1)  # Volume 0-1
    engine.say(message)
    engine.runAndWait()

# Function to create Excel file name based on the current date
def get_excel_file():
    now = datetime.now()
    date_str = now.strftime("%d-%m-%Y")
    return f'entry_exit_records_{date_str}.xlsx'

# Function to recognize faces
def recognize_face(face_encoding, known_face_encodings, known_face_names, known_face_designations):
    matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
    name = "Unknown"
    designation = ""

    if True in matches:
        first_match_index = matches.index(True)
        name = known_face_names[first_match_index]
        designation = known_face_designations[first_match_index]

    return name, designation

# Function to save intruder face data
def save_intruder_face(frame, top, right, bottom, left, face_encoding):
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d-%H-%M-%S")
    face_image = frame[top:bottom, left:right]
    filename = f"intruder/Intruder-{timestamp}.jpg"
    if not os.path.exists('intruder'):
        os.makedirs('intruder')
    cv2.imwrite(filename, face_image)
    print(f"Intruder detected. Saved as {filename}")
    intruder_data.append((face_encoding, filename))

# Function to update entry and exit records
def update_entry_exit_records(name, designation, enter_time, exit_time=None):
    excel_file = get_excel_file()

    if not os.path.exists(excel_file):
        df = pd.DataFrame(columns=['Name', 'Designation', 'Enter Time', 'Exit Time'])
    else:
        df = pd.read_excel(excel_file)

    if pd.isnull(enter_time):
        enter_time_str = "Unknown"
    else:
        enter_time_str = pd.Timestamp(enter_time).strftime("%Y-%m-%d %H:%M:%S")

    if exit_time:
        exit_time_str = pd.Timestamp(exit_time).strftime("%Y-%m-%d %H:%M:%S")
        df['Exit Time'] = df['Exit Time'].astype('object')
        df.loc[(df['Name'] == name) & (df['Designation'] == designation) & (df['Exit Time'].isnull()), 'Exit Time'] = exit_time_str
    else:
        existing_entries = df[(df['Name'] == name) & (df['Designation'] == designation) & (df['Exit Time'].isnull())]
        if existing_entries.empty:
            new_entry = pd.DataFrame({'Name': [name], 'Designation': [designation], 'Enter Time': [enter_time_str], 'Exit Time': [pd.NaT]})
            df = pd.concat([df, new_entry], ignore_index=True)

    df.to_excel(excel_file, index=False)

# Function to process frames and perform face recognition
def process_frames(cap, role, known_face_encodings, known_face_names, known_face_designations):
    while True:
        ret, frame = cap.read()
        if not ret:
            print(f"Error: Failed to capture frame from {role}. VideoCapture status:", cap.isOpened())
            break

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            name, designation = recognize_face(face_encoding, known_face_encodings, known_face_names, known_face_designations)
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(frame, f"{name} ({designation})", (left + 6, bottom - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if role == "entry gate" and name != "Unknown":
                update_entry_exit_records(name, designation, now)
            elif role == "exit gate" and name != "Unknown":
                update_entry_exit_records(name, designation, None, now)
            elif role == "restricted area":
                if name == "Unknown" or not restricted_area_access.get(designation.lower(), False):
                    play_warning(f"You are unauthorized to enter this section, {name}")
                    save_intruder_face(frame, top, right, bottom, left, face_encoding)
            if name == "Unknown" and not any(face_recognition.compare_faces([data[0] for data in intruder_data], face_encoding)):
                save_intruder_face(frame, top, right, bottom, left, face_encoding)
                play_warning("Intruder Detected")
        window_name = f'Face Recognition - {role}'
        cv2.imshow(window_name, frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

# Function to load known faces
def load_known_faces(known_faces_dir):
    known_face_encodings = []
    known_face_names = []
    known_face_designations = []

    if not os.path.exists(known_faces_dir):
        os.makedirs(known_faces_dir)

    for category in ["students", "admins", "teachers", "guests"]:
        category_dir = os.path.join(known_faces_dir, category)
        if not os.path.exists(category_dir):
            os.makedirs(category_dir)
        for filename in os.listdir(category_dir):
            image_path = os.path.join(category_dir, filename)
            image = face_recognition.load_image_file(image_path)
            encodings = face_recognition.face_encodings(image)
            if encodings:
                encoding = encodings[0]
                known_face_encodings.append(encoding)
                known_face_names.append(os.path.splitext(filename)[0])
                known_face_designations.append(category.capitalize()[:-1])

    return known_face_encodings, known_face_names, known_face_designations

# Function to start face recognition process for multiple cameras
def start_face_recognition(camera_roles, known_faces_dir):
    known_face_encodings, known_face_names, known_face_designations = load_known_faces(known_faces_dir)

    caps = []
    for role, indices in camera_roles.items():
        for index in indices:
            cap = cv2.VideoCapture(index)
            if cap.isOpened():
                caps.append((cap, role))

    if not caps:
        print("No cameras assigned. Please assign cameras before starting face recognition.")
        return

    while True:
        for cap, role in caps:
            ret, frame = cap.read()
            if not ret:
                print(f"Error: Failed to capture frame from {role}. VideoCapture status:", cap.isOpened())
                continue

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                name, designation = recognize_face(face_encoding, known_face_encodings, known_face_names, known_face_designations)
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.putText(frame, f"{name} ({designation})", (left + 6, bottom - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if role == "entry gate" and name != "Unknown":
                    update_entry_exit_records(name, designation, now)
                elif role == "exit gate" and name != "Unknown":
                    update_entry_exit_records(name, designation, None, now)
                elif role == "restricted area":
                    if name == "Unknown" or not restricted_area_access.get(designation.lower(), False):
                        print(f"Warning: Unauthorized access attempt by {name} ({designation})")
                        play_warning(f"You are unauthorized to enter this section, {name}")
                if name == "Unknown" and not any(face_recognition.compare_faces([data[0] for data in intruder_data], face_encoding)):
                    save_intruder_face(frame, top, right, bottom, left, face_encoding)
                    play_warning("Intruder Detected")
            window_name = f'Face Recognition - {role}'
            cv2.imshow(window_name, frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            for cap, _ in caps:
                cap.release()
            cv2.destroyAllWindows()
            return

# Function to detect available cameras
def detect_cameras():
    index = 0
    arr = []
    while True:
        cap = cv2.VideoCapture(index)
        if not cap.isOpened():  
            # If the camera is not opened and the index is 0, it means no cameras are available
            if index == 0:
                print("No cameras detected.")
            break
        else:
            arr.append(index)
            cap.release()
        index += 1
    return arr

# Function to add a new face
def add_face(known_faces_dir):
    available_cameras = detect_cameras()
    if not available_cameras:
        print("No cameras detected. Please connect a camera to add a new face.")
        return
    os.system('cls')
    print_centered_text(art)
    print_centered_text("Available cameras")
    print()
  
    for i, cam in enumerate(available_cameras):
        #print(f"{i + 1}. Camera {cam}")
        print_centered_text(f"{i + 1}. Camera {cam}")
                            
    cam_index = int(input("Select camera number to capture new face: ")) - 1
    cap = cv2.VideoCapture(available_cameras[cam_index])

    print("Press 'c' to capture a face for a new entry.")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to capture frame. Check camera status.")
            break

        cv2.imshow('Add New Face', frame)
        if cv2.waitKey(1) & 0xFF == ord('c'):
            break

    cap.release()
    cv2.destroyAllWindows()
    
    face_name = input("Enter name: ")

    os.system('color 2')
    os.system('cls') 
    print_centered_text(art)
    print()
    print_centered_text("Select category:    ")
    print_centered_text("1. Students         ")
    print_centered_text("2. Admins           ")
    print_centered_text("3. Teachers         ")
    print_centered_text("4. Guests           ")
    
    
    valide_range=[1,2,3,4]
    category_index = int(input("Enter the number corresponding to the category: "))
    
    if (category_index not in valide_range):
        print("Invalid choice. Please try again.")
        time.sleep(1)
        add_face(known_faces_dir)
    category_map = {1: "students", 2: "admins", 3: "teachers", 4: "guests"}
    category = category_map[category_index]

    category_dir = os.path.join(known_faces_dir, category)
    if not os.path.exists(category_dir):
        os.makedirs(category_dir)

    filename = f"{face_name}.jpg"
    filepath = os.path.join(category_dir, filename)
    cv2.imwrite(filepath, frame)
    print(f"Face for {face_name} saved at {filepath}")

# Function to delete a face
def delete_face(known_faces_dir):
    os.system('cls')
    print_centered_text(art)
    print("\n")
    print_centered_text("Select category to delete face from ")
    print_centered_text("1. Students")
    print_centered_text("2. Admins  ")
    print_centered_text("3. Teachers")
    print_centered_text("4. Guests  ")
    
    category_index = int(input("Enter the number corresponding to the category: "))
    valide_range=[1,2,3,4]
    if (category_index not in valide_range):
        print("Invalid choice. Please try again.")
        time.sleep(1.5)
        delete_face()
    category_map = {1: "students", 2: "admins", 3: "teachers", 4: "guests"}
    category = category_map[category_index]

    category_dir = os.path.join(known_faces_dir, category)
    if not os.path.exists(category_dir):
        print(f"Category {category} does not exist.")
        return
    os.system('cls')
    print_centered_text(art)
    print("\n")
    print_centered_text(f"Faces in {category.capitalize()}")
    faces = os.listdir(category_dir)
    for i, filename in enumerate(faces):
        print_centered_text(f"{i + 1}. {filename}")
    print()
    face_index = int(input("Enter the number corresponding to the face to delete: ")) - 1
    face_name = os.path.splitext(faces[face_index])[0]
    filepath = os.path.join(category_dir, f"{face_name}.jpg")
    if os.path.exists(filepath):
        os.remove(filepath)
        print(f"Face {face_name} deleted.")
    else:
        print(f"Face {face_name} not found in category {category}.")

# Function to assign cameras to roles
# Function to assign cameras to roles
def assign_camera():
    for key in camera_roles:
        camera_roles[key] = []
    available_cameras = detect_cameras()
    
    if not available_cameras:
        print("No cameras detected. Please connect a camera.")
        return
    os.system('cls')
    print_centered_text(art)
    print("\n")
    print_centered_text(f"Connected cameras: {len(available_cameras)}")
    print("\n")
    
    
    while True:
        try:
            num_cameras = int(input("How many cameras are you going to use? "))
            if num_cameras > len(available_cameras):
                print(f"Error: You only have {len(available_cameras)} available cameras.")
            else:
                break
        except ValueError:
            print("Please enter a valid number.")
    
    for i in range(num_cameras):
        os.system('cls')
        print_centered_text(art)
        print("\n")
        print_centered_text(f"Assign a role to camera {available_cameras[i]}")
        print_centered_text("1. Entry Gate     ")
        print_centered_text("2. Exit Gate      ")
        print_centered_text("3. Restricted Area")
        print_centered_text("4. Classroom      ")
        print_centered_text("5. Ordinary Camera")
        valide_range=[1,2,3,4,5]
        role = int(input("Enter the number corresponding to the role: "))
       
        if (role not in valide_range):
            print("Invalid choice. Please try again.")
            time.sleep(1.5)
            assign_camera()
        
        if role == 3:
            os.system('cls')
            print_centered_text(art)
            print("\n")
            print_centered_text("Choose Access of the Restricted Area By Role")
            print_centered_text("1. Student")
            print_centered_text("2. Admin  ")
            print_centered_text("3. Teacher")
            print_centered_text("4. Guest  ")
            access_info = input("Give numorical input role who can access this area numbere's are separeted by space : ")
            access = access_info.split()
            access_map = {1: "student", 2: "admin", 3: "teacher", 4: "guest"}
            for j in range(1, 5):
                restricted_area_access[access_map[i]] = str(i) in access

        role_name = role_map[role]
        camera_roles[role_name].append(available_cameras[i])
        print(f"Camera {available_cameras[i]} assigned to {role_name}")

def track_person(known_faces_dir):
    known_face_encodings, known_face_names, known_face_designations = load_known_faces(known_faces_dir)
    os.system('cls')
    print_centered_text(art)
    print("\n")
    print_centered_text("Available Faces to Track ")
    av=1
    for i, name in enumerate(known_face_names):
        print_centered_text(f"{i + 1}. {name} ({known_face_designations[i]})")
        av+=i
    print_centered_text(f"{av+1}. Back to Main Menu")
    
    person_index = int(input("Enter the number corresponding to the person to track: ")) - 1
    print()
    if person_index < 0 or person_index >= len(known_face_encodings):
        print("Invalid selection.")
        time.sleep(1.5)
        track_person()

    person_encoding = known_face_encodings[person_index]
    person_name = known_face_names[person_index]

    caps = []
    for role, indices in camera_roles.items():
        for index in indices:
            cap = cv2.VideoCapture(index)
            if cap.isOpened():
                caps.append((cap, role))

    if not caps:
        print("No cameras assigned. Please assign cameras before tracking a person.")
        time.sleep(3)
        return

    while True:
        found = False
        for cap, role in caps:
            ret, frame = cap.read()
            if not ret:
                print(f"Error: Failed to capture frame from {role}. VideoCapture status:", cap.isOpened())
                time.sleep(2)
                continue

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                matches = face_recognition.compare_faces([person_encoding], face_encoding)
                if True in matches:
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                    cv2.putText(frame, f"{person_name}", (left + 6, bottom - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    print(f"{person_name} located at {role}")

                    play_warning(f"{person_name} located at {role}")

                    found = True
                    break

            window_name = f'Track Person - {role}'
            cv2.imshow(window_name, frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            for cap, _ in caps:
                cap.release()
            cv2.destroyAllWindows()
            break

PASSWORD_FILE = "admin_password.hash"



def setup_password():
    while True:
        os.system('color 2')
        os.system('cls')
        print_centered_text(art)
        print("\n")
        password = getpass.getpass("Set up your admin password: ")
        confirm_password = getpass.getpass("Confirm your admin password: ")
        if password != confirm_password:
            print("Passwords do not match. Please try again.")
            time.sleep(1.5)
        else:
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            with open(PASSWORD_FILE, 'wb') as f:
                f.write(hashed)
            print("Admin password setup complete.")
            break

def verify_password():
    while True:
        os.system('color 2')
        os.system('cls')
        print_centered_text(art)
        print("\n")
        if not os.path.exists(PASSWORD_FILE):
            print("Admin password not set up. Please set it up first.")
            setup_password()

        password = getpass.getpass("Enter your admin password: ")
        with open(PASSWORD_FILE, 'rb') as f:
            stored_hash = f.read()

        if bcrypt.checkpw(password.encode(), stored_hash):
            return True
        else:
            print("Wrong password. Please try again.")
            time.sleep(1.5)

def change_password():
    os.system('color 2')
    os.system('cls')
    print_centered_text(art)
    print("\n")
    if verify_password():
        print("Verify your current password.")
        setup_password()


def main_menu():
    
    while True:
        os.system('color 2')
        os.system('cls')
        
        print_centered_text(art)
        print_centered_text("------Main Menu------\n")
        print_centered_text("1. Add Face              ")
        print_centered_text("2. Delete Face           ")
        print_centered_text("3. Assign Camera         ")
        print_centered_text("4. Start Face Recognition")
        print_centered_text("5. Track Person          ")
        print_centered_text("6. Change Admin Password ")
        print_centered_text("7. Exit                  ")
        print()
        choice = input("Enter your choice: ")
        
        if choice == '1':
            add_face('known_faces')
        elif choice == '2':
            delete_face('known_faces')
        elif choice == '3':
            assign_camera()
        elif choice == '4':
            known_face_encodings, known_face_names, known_face_designations = load_known_faces('known_faces')
            if known_face_encodings:
                start_face_recognition(camera_roles, 'known_faces')
            else:
                print_centered_text("No known faces loaded. Please add faces before starting face recognition.")
        elif choice == '5':
            track_person('known_faces')
        elif choice == '6':
            change_password()
        elif choice == '7':
            os.system('exit')
            break
            
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    if verify_password():
        main_menu()