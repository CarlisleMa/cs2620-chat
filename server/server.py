import socket

HOST = "127.0.0.1"
PORT = 54400

def translate_to_pig_latin(text):
    """Convert words to Pig Latin."""
    words = text.split()
    pig_latin_words = []
    
    for word in words:
        if word[0] in "aeiouAEIOU":
            pig_latin = word + "way"
        else:
            pig_latin = word[1:] + word[0] + "ay"
        pig_latin_words.append(pig_latin)
    
    return " ".join(pig_latin_words)

if __name__ == "__main__":
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server listening on {HOST}:{PORT}")

        conn, addr = s.accept()
        with conn:
            print(f"Connected by {addr}")
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                
                data = data.decode("utf-8")
                return_data = translate_to_pig_latin(data)
                return_data = return_data.encode("utf-8")
                
                conn.sendall(return_data)
                print(f"Received: {data}")
                print(f"Sent: {return_data.decode()}")

        print("Client disconnected.")
