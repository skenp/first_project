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
import zlib

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

fps=30

mouse_down = False
mouse_lmr = False
mouse_move = False

keyboard_input = 0

def resize_block_8x8_to_full(blocks, width, height):
    blocks = np.array(blocks)
    blocks = blocks.reshape(height // 8, width // 8, 8, 8)
    result = blocks.transpose(0,2,1,3).reshape(height,width)
    return result[:receive_height, :receive_width].astype(np.uint8)
    # rows = []
    # for i in range(0, len(blocks), int(padded_width/8)): # 가로로 탐색
    #     rows.append(np.hstack(blocks[i:i+int(padded_width/8)])) # 가로인 모든 블록들 합치기
    # result_arr = np.vstack(rows)
    # return result_arr[:receive_height, :receive_width].astype(np.uint8)

def idct_and_dequantization(img, Y_or_C):
    if Y_or_C == 'Y':
        Q_table = np.array([ 
        [16,11,10,16,24,40,51,61],
        [12,12,14,19,26,58,60,55],
        [14,13,16,24,40,57,69,56],
        [14,17,22,29,51,87,80,62],
        [18,22,37,56,68,109,103,77],
        [24,35,55,64,81,104,113,92],
        [49,64,78,87,103,121,120,101],
        [72,92,95,98,112,100,103,99]], dtype=np.float32) # 양자화 테이블 이건 정해진거 바꾸기 X (상수)
    elif Y_or_C == 'C':
        Q_table = np.array([ 
        [17,18,24,47,99,99,99,99],
        [18,21,26,66,99,99,99,99],
        [24,26,56,99,99,99,99,99],
        [47,66,99,99,99,99,99,99],
        [99,99,99,99,99,99,99,99],
        [99,99,99,99,99,99,99,99],
        [99,99,99,99,99,99,99,99],
        [99,99,99,99,99,99,99,99]], dtype=np.float32) # 양자화 테이블 이건 정해진거 바꾸기 X (상수)

    result_arr = np.zeros_like(img, dtype=np.float32)

    for i, block in enumerate(img): 
        result_arr[i] = np.round(cv2.idct(block*Q_table)+128)

    return result_arr
        
def temp(): # 화면받는 함수, pygame 이벤트 처리
    bool = True
    global mouse_down, mouse_lmr, mouse_move, keyboard_input
    screen = pygame.display.set_mode((width_scale, height_scale))
    pygame.display.set_caption("screen sharing")
    pygame.init()
    clock = pygame.time.Clock()
    while True:
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

            buf_Y_arr = np.frombuffer(zlib.decompress(Y_receive_data), dtype=np.int16).reshape(Y_elements, 8, 8)
            buf_Cb_arr = np.frombuffer(zlib.decompress(Cb_receive_data), dtype=np.int16).reshape(Cb_elements, 8, 8)
            buf_Cr_arr = np.frombuffer(zlib.decompress(Cr_receive_data), dtype=np.int16).reshape(Cr_elements, 8, 8)

            buf_Y_arr = idct_and_dequantization(buf_Y_arr, Y_or_C='Y') # 디코딩
            buf_Cb_arr = idct_and_dequantization(buf_Cb_arr, Y_or_C='C')
            buf_Cr_arr = idct_and_dequantization(buf_Cr_arr, Y_or_C='C')

            buf_Y_arr = resize_block_8x8_to_full(buf_Y_arr, padded_width, padded_height) # 1440, 2560으로 블록 합치기 
            buf_Cb_arr = resize_block_8x8_to_full(buf_Cb_arr, padded_width, padded_height)
            buf_Cr_arr = resize_block_8x8_to_full(buf_Cr_arr, padded_width, padded_height)

            result_YCrCb = np.stack([buf_Y_arr, buf_Cr_arr, buf_Cb_arr], axis=2) # YCrCb순서로 합치기

            RGB_img = cv2.cvtColor(result_YCrCb, cv2.COLOR_YCrCb2RGB)
            surface = pygame.surfarray.make_surface(np.swapaxes(RGB_img, 0, 1)) # width, height 순서 바꾸기

            show_img = pygame.transform.scale(surface, (width_scale, height_scale))
            
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
                    dx_dy_receive_data+=screen_client_socket.recv(dx_dy_long-len(dx_dy_receive_data)) 
                Y_receive_data=b'' 
                while len(Y_receive_data)<Y_long:
                    Y_receive_data+=screen_client_socket.recv(Y_long-len(Y_receive_data)) 
                Cb_receive_data=b'' 
                while len(Cb_receive_data)<Cb_long:
                    Cb_receive_data+=screen_client_socket.recv(Cb_long-len(Cb_receive_data)) 
                Cr_receive_data=b'' 
                while len(Cr_receive_data)<Cr_long:
                    Cr_receive_data+=screen_client_socket.recv(Cr_long-len(Cr_receive_data)) 


                dxdy_arr = np.frombuffer(zlib.decompress(dx_dy_receive_data), dtype=np.int16).reshape(-1, 2)
                dx_dy = [tuple(i) for i in dxdy_arr.tolist()] # 튜플가진 리스트로 변환

                Y_arr = np.frombuffer(zlib.decompress(Y_receive_data), dtype=np.int16).reshape(Y_elements, 8, 8)
                Cb_arr = np.frombuffer(zlib.decompress(Cb_receive_data), dtype=np.int16).reshape(Cb_elements, 8, 8)
                Cr_arr = np.frombuffer(zlib.decompress(Cr_receive_data), dtype=np.int16).reshape(Cr_elements, 8, 8)



                # 잔차
                Y_idct_deq = idct_and_dequantization(Y_arr, Y_or_C='Y')
                Cb_idct_deq = idct_and_dequantization(Cb_arr, Y_or_C='C')
                Cr_idct_deq = idct_and_dequantization(Cr_arr, Y_or_C='C')

                # if bool == True:
                #     for v in range(4):
                #         print(Y_idct_deq[720*4+v])
                #     bool = False

                #p-frame 복원
                
                result_Y = np.zeros((padded_height, padded_width), dtype=np.uint8) # 일단 선언
                result_Cb = np.zeros((padded_height, padded_width), dtype=np.uint8)
                result_Cr = np.zeros((padded_height, padded_width), dtype=np.uint8)


                k = 0  # 8x8 잔차 블록의 인덱스
                for i, (dx, dy) in enumerate(dx_dy):
                    x = (i % (padded_width // 16)) * 16
                    y = (i // (padded_width // 16)) * 16

                    i_x = x - dx # 블록 크기인 16만큼 곱하고 dx더하기
                    i_y = y - dy # 블록 크기인 16만큼 곱하고 dy더하기

                    i_x = max(0, min(i_x, padded_width - 16))
                    i_y = max(0, min(i_y, padded_height - 16))

                    ref_block_16_Y = buf_Y_arr[i_y:i_y+16, i_x:i_x+16]
                    ref_block_16_Cb = buf_Cb_arr[i_y:i_y+16, i_x:i_x+16]
                    ref_block_16_Cr = buf_Cr_arr[i_y:i_y+16, i_x:i_x+16]

                    ref_blocks_Y = [ # 8x8 4블록으로 나누기
                        ref_block_16_Y[0:8, 0:8],
                        ref_block_16_Y[0:8, 8:16],
                        ref_block_16_Y[8:16, 0:8],
                        ref_block_16_Y[8:16, 8:16]
                    ]
                    ref_blocks_Cb = [
                        ref_block_16_Cb[0:8, 0:8],
                        ref_block_16_Cb[0:8, 8:16],
                        ref_block_16_Cb[8:16, 0:8],
                        ref_block_16_Cb[8:16, 8:16]
                    ]
                    ref_blocks_Cr = [
                        ref_block_16_Cr[0:8, 0:8],
                        ref_block_16_Cr[0:8, 8:16],
                        ref_block_16_Cr[8:16, 0:8],
                        ref_block_16_Cr[8:16, 8:16]
                    ]

                    for o in range(4): # 위치마다 저장
                        sub_x = x + (8 * (o % 2))
                        sub_y = y + (8 * (o // 2))

                        result_Y[sub_y:sub_y+8, sub_x:sub_x+8] = np.clip(ref_blocks_Y[o] + Y_idct_deq[k], 0, 255).astype(np.uint8)
                        result_Cb[sub_y:sub_y+8, sub_x:sub_x+8] = np.clip(ref_blocks_Cb[o] + Cb_idct_deq[k], 0, 255).astype(np.uint8)
                        result_Cr[sub_y:sub_y+8, sub_x:sub_x+8] = np.clip(ref_blocks_Cr[o] + Cr_idct_deq[k], 0, 255).astype(np.uint8)
                        k += 1

                result_Y = result_Y[:receive_height, :receive_width]
                result_Cb = result_Cb[:receive_height, :receive_width]
                result_Cr = result_Cr[:receive_height, :receive_width]
                
                # np.set_printoptions(threshold=sys.maxsize)

                # if bool == True:
                #     print(result_Y.shape)
                #     bool = False

                result_YCrCb = np.stack([result_Y, result_Cr, result_Cb], axis=2) # YCrCb순서로 합치기
                # np.set_printoptions(threshold=sys.maxsize)

                # if bool == True:
                #     print(result_Y.shape)
                #     bool = False

                RGB_img = cv2.cvtColor(result_YCrCb, cv2.COLOR_YCrCb2RGB)
                surface = pygame.surfarray.make_surface(np.swapaxes(RGB_img, 0, 1)) # width, height 순서 바꾸기

                show_img = pygame.transform.scale(surface, (width_scale, height_scale))
                
                screen.blit(show_img, (0,0))
                pygame.display.update()

                buf_Y_arr, buf_Cb_arr, buf_Cr_arr = result_Y, result_Cb, result_Cr
                print(1)

                

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
