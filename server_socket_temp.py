import socket
from PIL import Image
import io
import pyautogui
import sys
import threading
import struct
import os
import time
import numpy as np
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1' # pygame 출력 가리
import pygame
import cv2

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
while len(receive_scale)<16:
    receive_scale += screen_client_socket.recv(16-len(receive_scale))

receive_width, receive_height, padded_width, padded_height = struct.unpack('>I I I I', receive_scale)

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

def Y_idct_and_dequantization(img, img_elements):

    result_arr = []

    Q_table = np.array([ 
    [16,11,10,16,24,40,51,61],
    [12,12,14,19,26,58,60,55],
    [14,13,16,24,40,57,69,56],
    [14,17,22,29,51,87,80,62],
    [18,22,37,56,68,109,103,77],
    [24,35,55,64,81,104,113,92],
    [49,64,78,87,103,121,120,101],
    [72,92,95,98,112,100,103,99]], dtype=np.float32) # 양자화 테이블 이건 정해진거 바꾸기 X (상수)

    for block in img:
        result_arr.append(cv2.idct(block.astype(np.float32)*Q_table))
    return result_arr


def convert_16x16_Y(blocks):
    result_arr = []
    for i in range(0, len(blocks), 4):
        b0, b1, b2, b3 = blocks[i:i+4]

        top = np.hstack([b0, b1])   # 각각 가로로 결합
        bottom = np.hstack([b2, b3]) 

        result_arr.append(np.vstack([top, bottom]))  # 세로로 결합
    return result_arr

def Y_idct_and_dequantization(img):
    result_arr = []

    Q_table = np.array([ 
    [16,11,10,16,24,40,51,61],
    [12,12,14,19,26,58,60,55],
    [14,13,16,24,40,57,69,56],
    [14,17,22,29,51,87,80,62],
    [18,22,37,56,68,109,103,77],
    [24,35,55,64,81,104,113,92],
    [49,64,78,87,103,121,120,101],
    [72,92,95,98,112,100,103,99]], dtype=np.float32) # 양자화 테이블 이건 정해진거 바꾸기 X (상수)

    for block in img:
        result_arr.append(cv2.idct(block.astype(np.float32)*Q_table))
    result_arr = np.stack(result_arr, axis=0) # 3차원 배열로
    return result_arr

def CbCr_idct_and_dequantization(img):

    result_arr = []

    Q_table = np.array([ 
    [17,18,24,47,99,99,99,99],
    [18,21,26,66,99,99,99,99],
    [24,26,56,99,99,99,99,99],
    [47,66,99,99,99,99,99,99],
    [99,99,99,99,99,99,99,99],
    [99,99,99,99,99,99,99,99],
    [99,99,99,99,99,99,99,99],
    [99,99,99,99,99,99,99,99]], dtype=np.float32) # 양자화 테이블 이건 정해진거 바꾸기 X (상수)

    for block in img:
        result_arr.append(cv2.idct(block.astype(np.float32)*Q_table))
    result_arr = np.stack(result_arr, axis=0) # 3차원 배열로
    return result_arr
    

def convert_16x16(blocks):
    result_arr = []
    for i in range(0, len(blocks), 4):
        b0, b1, b2, b3 = blocks[i:i+4]

        top = np.hstack([b0, b1])   # 각각 가로로 결합
        bottom = np.hstack([b2, b3]) 

        result_arr.append(np.vstack([top, bottom]))  # 세로로 결합
    return result_arr



def temp(): # 화면받는 함수, pygame 이벤트 처리
    screen = pygame.display.set_mode((width_scale, height_scale))
    pygame.display.set_caption("screen sharing")
    pygame.init()
    clock = pygame.time.Clock()

    clock.tick(fps)
    global mouse_down, mouse_lmr, mouse_move, keyboard_input
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



        # i-frame 처리
        header=b'' # 길이 먼저 받기
        while len(header)<24:
            header+=screen_client_socket.recv(24-len(header))
        Y_elements, Cb_elements, Cr_elements, Y_long, Cb_long, Cr_long = struct.unpack('>I I I I I I', header)

        # 데이터 길이 만큼 받기
        Y_receive_data=b'' 
        while len(Y_receive_data)<Y_long:
            Y_receive_data+=screen_client_socket.recv(Y_long-len(Y_receive_data)) 
        Cb_receive_data=b'' 
        while len(Cb_receive_data)<Cb_long:
            Cb_receive_data+=screen_client_socket.recv(Cb_long-len(Cb_receive_data)) 
        Cr_receive_data=b'' 
        while len(Cr_receive_data)<Cr_long:
            Cr_receive_data+=screen_client_socket.recv(Cr_long-len(Cr_receive_data)) 

        Y_arr = np.frombuffer(Y_receive_data, dtype=np.int16).reshape(Y_elements, 8, 8)
        Cb_arr = np.frombuffer(Cb_receive_data, dtype=np.int16).reshape(Cb_elements, 8, 8)
        Cr_arr = np.frombuffer(Cr_receive_data, dtype=np.int16).reshape(Cr_elements, 8, 8)

        Cb_arr = np.repeat(Cb_arr, 2)
        Cr_arr = np.repeat(Cr_arr, 2)

        Y_arr = Y_idct_and_dequantization(Y_arr)
        Cb_arr = CbCr_idct_and_dequantization(Cb_arr)
        Cr_arr = CbCr_idct_and_dequantization(Cr_arr)

        Y_arr = Y_arr.reshape(padded_height, padded_width)
        Cb_arr = Cb_arr.reshape(padded_height, padded_width)
        Cr_arr = Cr_arr.reshape(padded_height, padded_width)

        result_YCrCb = np.stack([Y_arr, Cr_arr,  Cb_arr], axis=2)

        RGB_img = cv2.cvtColor(result_YCrCb, cv2.COLOR_YCrCb2RGB)


        show_img = pygame.transform.scale(RGB_img, (width_scale, height_scale))
        
        screen.blit(show_img, (0,0))
        pygame.display.update()

        # p-frame
        for j in range(15):
            clock.tick(fps)

            header=b'' # 길이 먼저 받기
            while len(header)<28:
                header+=screen_client_socket.recv(28-len(header))
            Y_elements, Cb_elements, Cr_elements, dx_dy_long, Y_long, Cb_long, Cr_long = struct.unpack('>I I I I I I I', header)
            
            # 데이터 길이 만큼 받기
            dx_dy_receive_data=b'' 
            while len(dx_dy_receive_data)<dx_dy_long:
                dx_dy_receive_data+=screen_client_socket.recv(Y_long-len(dx_dy_receive_data)) 
            Y_receive_data=b'' 
            while len(Y_receive_data)<Y_long:
                Y_receive_data+=screen_client_socket.recv(Y_long-len(Y_receive_data)) 
            Cb_receive_data=b'' 
            while len(Cb_receive_data)<Cb_long:
                Cb_receive_data+=screen_client_socket.recv(Cb_long-len(Cb_receive_data)) 
            Cr_receive_data=b'' 
            while len(Cr_receive_data)<Cr_long:
                Cr_receive_data+=screen_client_socket.recv(Cr_long-len(Cr_receive_data)) 


            dxdy_arr = np.frombuffer(dx_dy_receive_data, dtype=np.int16).reshape(-1, 2)
            dx_dy = [tuple(i) for i in dxdy_arr.tolist()]

            Y_arr = np.frombuffer(Y_receive_data, dtype=np.int16).reshape(Y_elements, 8, 8)
            Cb_arr = np.frombuffer(Cb_receive_data, dtype=np.int16).reshape(Cb_elements, 8, 8)
            Cr_arr = np.frombuffer(Cr_receive_data, dtype=np.int16).reshape(Cr_elements, 8, 8)

            Y_idct_deq = Y_idct_and_dequantization(Y_arr, Y_elements)

            Y_16x16_arr = convert_16x16_Y(Y_idct_deq)
            
            # screen.blit(show_img, (0,0))
            pygame.display.update()

def screen_get(): # 화면받는 함수, pygame 이벤트 처리
    screen = pygame.display.set_mode((width_scale, height_scale))
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


screen_thread = threading.Thread(target=temp)
screen_thread.start()

mouse_thread = threading.Thread(target=mouse_send)
mouse_thread.start()

keyboard_thread = threading.Thread(target=keyboard_send)
keyboard_thread.start()
