import socket
import pyautogui
import threading
import io
import struct

pyautogui.FAILSAFE = False

print("write server adress")
server_address = input()

screen_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
mouse_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
keyboard_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

screen_client_socket.connect((server_address,8843))
mouse_client_socket.connect((server_address,8844))
keyboard_client_socket.connect((server_address,8845))

print("connected")

width, height = pyautogui.size() # 화면 픽셀

send_scale = struct.pack('>I I', width, height) # 빅엔디안 unsigned int로 바이트화

screen_client_socket.send(send_scale) # 화면 비율 보내기

def screen_send():
    while True:
        data=pyautogui.screenshot() # 화면 캡쳐후 image객체로 생성

        byte_stream = io.BytesIO() # 이미지를 바이트로 인코딩
        data.save(byte_stream, format='PNG')
        send_img = byte_stream.getvalue()

        how_bytes_long = len(send_img)
        send_long = struct.pack('>I', how_bytes_long) # 빅엔디안 unsigned int로 바이트화

        send_data = send_long+send_img # 길이와 이미지 결합
        screen_client_socket.send(send_data) # (바이트 길이 + 이미지) 보내기

def mouse_receive():
    current_mouse_state='u'
    mouse_lmr=0
    left_middle_right=['left','middle','right']
    while True:
        mouse_receive_data=b''
        while len(mouse_receive_data)<11: #마우스 위치,클릭 여부 받기
            mouse_receive_data += mouse_client_socket.recv(11-len(mouse_receive_data))
        mouse_x, mouse_y, mouse_lmr, mouse_down = struct.unpack('>I I H ?', mouse_receive_data)

        pyautogui.moveTo(mouse_x, mouse_y)

        if current_mouse_state=='u' and mouse_down == True:
            current_mouse_state = 'd'
            pyautogui.mouseDown(button=left_middle_right[mouse_lmr])
        elif current_mouse_state=='d' and mouse_down == False:
            current_mouse_state = 'u'
            pyautogui.mouseUp(button=left_middle_right[mouse_lmr])

def keyboard_receive():
    buf_key=''
    while 1:
        key_receive_data=b''
        while len(key_receive_data) < 4:
            key_receive_data += keyboard_client_socket.recv(4-len(key_receive_data))
        
        key = struct.unpack('> I', key_receive_data)[0]

        try:
            if key == 0:
                pyautogui.keyUp(buf_key)
            else :
                buf_key=chr(key)
                pyautogui.keyDown(buf_key)
        except:
            1


screen_thread = threading.Thread(target=screen_send)
screen_thread.start()

mouse_thread = threading.Thread(target=mouse_receive)
mouse_thread.start()

keyboard_thread = threading.Thread(target=keyboard_receive)
keyboard_thread.start()
