import socket
from PIL import Image
import io
import pyautogui
import sys
import threading
import struct
import os
import time
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1' # pygame 출력 가리기
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pygame.pkgdata")
import pygame


my_ip = socket.gethostbyname(socket.gethostname()) # 내 아이피

screen_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # 화면 받는 소켓 생성
screen_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

screen_server_socket.bind((my_ip, 8843))

mouse_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # 마우스 보내는 소켓 생성
mouse_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

mouse_server_socket.bind((my_ip, 8844))

keyboard_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # 키보드 보내는 소켓 생성
keyboard_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

keyboard_server_socket.bind((my_ip, 8845))

screen_server_socket.listen() # 소켓 기다리기
mouse_server_socket.listen()
keyboard_server_socket.listen()
print(my_ip+' socket waiting')

screen_client_socket, client_address = screen_server_socket.accept() # 요청 받기
mouse_client_socket, client_address = mouse_server_socket.accept()
keyboard_client_socket, client_address = keyboard_server_socket.accept()
print("connected from " + client_address[0]) 

my_width, my_height = pyautogui.size() # 내 화면 픽셀

receive_scale=b'' # 화면 픽셀 받기
while len(receive_scale)<8:
    receive_scale += screen_client_socket.recv(8-len(receive_scale))

receive_width, receive_height = struct.unpack('>I I', receive_scale)

correction = 0

if receive_height*my_width/receive_width<=my_height: # 비율 최적화
    correction = my_width/receive_width

    width_scale = my_width
    height_scale = receive_height*correction
else:
    correction = my_height/receive_height

    width_scale = receive_width*correction
    height_scale = my_height

fps=10

mouse_down = False
mouse_lmr = False
mouse_move = False

keyboard_input = 0

def screen_get(): # 화면받는 함수, pygame 이벤트 처리
    screen = pygame.display.set_mode((my_width, my_height))
    pygame.display.set_caption("screen sharing")
    pygame.init()
    clock = pygame.time.Clock()

    global mouse_down, mouse_lmr, mouse_move, keyboard_input

    while 1:
        clock.tick(fps)

        for event in pygame.event.get():
            if event.type==pygame.QUIT: # 프로그램 종료
                pygame.quit()
                screen_client_socket.close()
                mouse_client_socket.close()
                sys.exit()
            if event.type == pygame.MOUSEMOTION: #마우스 움직임 확인
                mouse_move=True
            if event.type == pygame.MOUSEBUTTONDOWN: # 마우스 클릭 확인
                if event.button == 1: # 왼쪽 클릭
                    mouse_lmr = 0
                elif event.button == 2: # 휠 클릭
                    mouse_lmr = 1
                elif event.button == 3: # 오른쪽 클릭
                    mouse_lmr = 2
                mouse_down = True
            if event.type == pygame.MOUSEBUTTONUP:
                mouse_down = False
            if event.type == pygame.KEYDOWN:
                keyboard_input = int(event.key)
            if event.type == pygame.KEYUP:
                keyboard_input = 0

        header=b'' # 길이 먼저 받기
        while len(header)<4:
            header+=screen_client_socket.recv(4-len(header))
        real_long=struct.unpack('>I', header)[0]
        

        receive_data=b'' 
        while len(receive_data)<real_long: # 데이터 길이 만큼 받기
            receive_data+=screen_client_socket.recv(real_long-len(receive_data)) 

        io_data = io.BytesIO(receive_data) # 이미지 디코딩
        PIL_img = Image.open(io_data)
        
        pygame_img = pygame.image.fromstring(PIL_img.tobytes(), PIL_img.size, PIL_img.mode) # PIL이미지 pygame으로 변환
        show_img = pygame.transform.scale(pygame_img, (width_scale, height_scale))
        
        screen.blit(show_img, (0,0))
        pygame.display.update()

def mouse_send():
    global mouse_down, mouse_lmr, mouse_move

    current_mouse_change = [mouse_down, mouse_lmr]
    while 1:
        mouse_x, mouse_y = pygame.mouse.get_pos() # 마우스 위치 확인

        mouse_x = int(mouse_x / correction) # 마우스 위치 조절
        mouse_y = int(mouse_y / correction) 
        

        send_mouse_pos = struct.pack('>I I H ?', mouse_x, mouse_y, mouse_lmr, mouse_down) # 보내기

        if mouse_move == True or mouse_down != current_mouse_change[0] or mouse_lmr != current_mouse_change[1]: #마우스에 변화가 있을때만 보내기
            mouse_client_socket.send(send_mouse_pos)
            mouse_move = False

        current_mouse_change[0] = mouse_down
        current_mouse_change[1] = mouse_lmr

        time.sleep(0.05)

def keyboard_send():
    global keyboard_input
    key_down_send = False

    while(True):
        current_key = keyboard_input
        send_key = struct.pack('> I', current_key)

        if current_key!=0 and key_down_send == False: # 키보드 입력시만 보내기 그리고 꾹 누르고 있으면 보내지 않기
            keyboard_client_socket.send(send_key)
            key_down_send = True
            print('first ',end='')
            print(current_key)

        elif current_key==0 and key_down_send == True: # 키를 때면 전송
            keyboard_client_socket.send(send_key) # 0전송 -> 키 올리라는 명령 전송
            key_down_send = False
            print('second ',end='')
            print(current_key)
        time.sleep(0.05)


screen_thread = threading.Thread(target=screen_get)
screen_thread.start()

mouse_thread = threading.Thread(target=mouse_send)
mouse_thread.start()

keyboard_thread = threading.Thread(target=keyboard_send)
keyboard_thread.start()
