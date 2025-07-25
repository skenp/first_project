import socket # 패딩 해야함
import pyautogui
import threading
import io
import struct
import numpy as np
import cv2
import zlib
import mss

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
block_size = 16


padded_width = width + (block_size-width%block_size)%block_size
padded_height = height + (block_size-height%block_size)%block_size

send_scale = struct.pack('>I I I I', width, height, padded_width, padded_height) # 빅엔디안 unsigned int로 바이트화

screen_client_socket.send(send_scale) # 화면 비율 보내기

def all_img_split_block(img, block_size_width, block_size_height): #p-frame용
    result_arr = [] # 블록들 저장할 배열

    for y in range(0, img.shape[0], block_size_height): # 세로만큼 반복
        for x in range(0, img.shape[1], block_size_width): # 가로만큼 반복
            result_arr.append((img[y:y+block_size_height, x:x+block_size_width], x, y)) # block과 시작 픽셀 저장
    
    return result_arr

def img_leave_proceeded_distance(img, dx, dy, start_x, start_y, block_size):#i-frame용 처리할 부분만 남기기 구하기
    return img[max(0, start_y-dy):min(padded_height, start_y+dy+block_size),
                max(0, start_x-dx):min(padded_width, start_x+dx+block_size)] # 이미지에서 처리할 부분만 남기기

def dct_and_quantization(residual_block, Y_or_C):
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

    # residual_8x8 = all_img_split_block(residual_block, 8, 8) # 16x16을 8x8로 변환

    result = []
    for y in range(0, residual_block.shape[0], 8):
        for x in range(0, residual_block.shape[1], 8):
            result.append(np.round(cv2.dct(residual_block[y:y+8, x:x+8].astype(np.float32) - 128) / Q_table))
    # for i in range(len(residual_8x8)):
    #     result.append(np.round(cv2.dct(residual_8x8[i][0].astype(np.float32)-128)/Q_table)) # level shift후 dct후 양자화한거 저장
    
    return result

def temp():
    sct = mss.mss() # mss 객체 생성
    monitor = {"top": 0, "left": 0, "width": width, "height": height} # 화면 모니터 생성

    while True:
        # i-frame 보내기
        buffer = np.array(sct.grab(monitor))

        buf_arr = buffer[:, :, :3] # i-frame 필요없는 alpha 짤라내기
        # block_size의 배수로 padding
        buf_arr = np.pad(buf_arr, ((0, padded_height-height), (0,padded_width-width), (0,0)), 'constant', constant_values=0)
        YCrCb_buf_arr = cv2.cvtColor(buf_arr, cv2.COLOR_BGR2YCrCb) # YCrCb 변환
        Y_buf_arr, Cr_buf_arr, Cb_buf_arr = cv2.split(YCrCb_buf_arr)
        buffer = (Y_buf_arr, Cr_buf_arr, Cb_buf_arr)

        Cb_buf_subsemplited=Cb_buf_arr # 4:4:4로 일단
        Cr_buf_subsemplited=Cr_buf_arr


        result_Y = dct_and_quantization(Y_buf_arr, Y_or_C='Y')
        result_Cb = dct_and_quantization(Cb_buf_subsemplited, Y_or_C='C')
        result_Cr = dct_and_quantization(Cr_buf_subsemplited, Y_or_C='C')

        send_result_Y = zlib.compress(np.stack(result_Y).astype(np.int16).tobytes())
        send_result_Cb = zlib.compress(np.stack(result_Cb).astype(np.int16).tobytes())
        send_result_Cr = zlib.compress(np.stack(result_Cr).astype(np.int16).tobytes())

        send_img = send_result_Y + send_result_Cb + send_result_Cr

        how_Y_elements_are = len(result_Y)
        how_Cb_elements_are = len(result_Cb)
        how_Cr_elements_are = len(result_Cr)
        how_Y_bytes_long = len(send_result_Y)
        how_Cb_bytes_long = len(send_result_Cb)
        how_Cr_bytes_long = len(send_result_Cr)

        send_long = struct.pack('>I I I I I I', how_Y_elements_are, how_Cb_elements_are, how_Cr_elements_are, how_Y_bytes_long, how_Cb_bytes_long, how_Cr_bytes_long) # 빅엔디안 unsigned int로 바이트화

        send_data = send_long+send_img # 길이와 이미지 결합
        screen_client_socket.send(send_data) # (바이트 길이 + 이미지) 보내기

        # p-frame 보내기
        for k in range(15):
            data=np.array(sct.grab(monitor)) # 화면 캡쳐 객체로 생성
            # frame 생성 작업
            img_arr = data[:, :, :3]  # p-frame alpha 짤라내기
            # block_size의 배수로 padding
            img_arr = np.pad(img_arr, ((0, padded_height-height), (0,padded_width-width), (0,0)), 'constant', constant_values=0)
            YCrCb_img_arr = cv2.cvtColor(img_arr, cv2.COLOR_BGR2YCrCb) # YCrCb로 변환값
            Y_img_arr, Cr_img_arr, Cb_img_arr = cv2.split(YCrCb_img_arr)

            # 일단 4:4:4
            Cb_img_subsemplited = Cb_img_arr
            Cr_img_subsemplited = Cr_img_arr

            Y_buf_arr, Cr_buf_arr, Cb_buf_arr = buffer # buffer 값 불러오기

            # 일단 4:4:4
            Cb_buf_subsemplited = Cb_buf_arr
            Cr_buf_subsemplited = Cr_buf_arr

            result_Y = [] # Y 압축 결과
            result_Cb = [] # Cb 압축 결과
            result_Cr = [] # Cr 압축 결과
            best_dx_dy = [] # SAD값이 가장 작은 블록의 dx, dy

            p_blocks = all_img_split_block(Y_img_arr, block_size, block_size) # 이미지 블록들 (Y)
            Cb_p_blocks = all_img_split_block(Cb_img_subsemplited, block_size, block_size)
            Cr_p_blocks = all_img_split_block(Cr_img_subsemplited, block_size, block_size)

            for i, (p_block, start_p_x_pos, start_p_y_pos) in enumerate(p_blocks): # p-blcok 블록마다 하는거임
                #잔차 과정(1)
                start_i_x_pos = max(0, start_p_x_pos-16)
                start_i_y_pos = max(0, start_p_y_pos-16)

                # i_blocks에 형태 [가능한 모든 블록](이미지, dx, dy)
                i_area = img_leave_proceeded_distance(Y_buf_arr, 16, 16, start_p_x_pos, start_p_y_pos, block_size) # p-frame의 시작점 기준 16거리안에서 i-frame블록 생성

                # SSD값이 가장 작은거 구하기 (범위는 탐색 범위 안)
                best_x, best_y = cv2.minMaxLoc(cv2.matchTemplate(i_area, p_block, cv2.TM_SQDIFF))[2] # 최적 블록 시작좌표

                #Y기준
                i_x, i_y = start_i_x_pos + best_x, start_i_y_pos + best_y # SSD값이 가장 작은 블록 x, y위치 (실제 i-frame위치)
                dx,dy = start_p_x_pos - i_x, start_p_y_pos - i_y
                best_dx_dy.append((dx, dy)) # SSD값이 가장 작은 블록의 dx, dy
                # Y 잔차
                Y_residual = (p_block - i_area[best_y:best_y+block_size, best_x:best_x+block_size])

                #Cb, Cr 잔차 
                Cb_residual = (Cb_p_blocks[i][0] - Cb_buf_subsemplited[i_y:i_y+block_size, i_x:i_x+block_size])
                Cr_residual = (Cr_p_blocks[i][0] - Cr_buf_subsemplited[i_y:i_y+block_size, i_x:i_x+block_size])


                # dct, 양자화 과정(2)
                result_Y.extend(dct_and_quantization(Y_residual, Y_or_C='Y'))
                result_Cb.extend(dct_and_quantization(Cb_residual, Y_or_C='C'))
                result_Cr.extend(dct_and_quantization(Cr_residual, Y_or_C='C'))

            # 보낼 데이터 int16, bytes형
            numpy_dx_dy = np.array(best_dx_dy)
            send_dx_dy = zlib.compress(numpy_dx_dy.astype(np.int16).tobytes())
            send_result_Y = zlib.compress(np.stack(result_Y).astype(np.int16).tobytes())
            send_result_Cb = zlib.compress(np.stack(result_Cb).astype(np.int16).tobytes())
            send_result_Cr = zlib.compress(np.stack(result_Cr).astype(np.int16).tobytes())

            send_img = send_dx_dy+send_result_Y+send_result_Cb+send_result_Cr

            how_Y_elements_are = len(result_Y)
            how_Cb_elements_are = len(result_Cb)
            how_Cr_elements_are = len(result_Cr)
            how_dx_dy_bytes_long = len(send_dx_dy)
            how_Y_bytes_long = len(send_result_Y)
            how_Cb_bytes_long = len(send_result_Cb)
            how_Cr_bytes_long = len(send_result_Cr)
            send_long = struct.pack('>I I I I I I I', how_Y_elements_are, how_Cb_elements_are, how_Cr_elements_are, how_dx_dy_bytes_long,how_Y_bytes_long, how_Cb_bytes_long, how_Cr_bytes_long) # 빅엔디안 unsigned int로 바이트화

            send_data = send_long+send_img # 길이와 이미지 결합
            screen_client_socket.send(send_data) # (바이트 길이 + 이미지) 보내기

            buffer = (Y_buf_arr, Cr_buf_arr, Cb_buf_arr)



def screen_send():
    while True:
        data=pyautogui.screenshot() # 화면 캡쳐후 image객체로 생성

        byte_stream = io.BytesIO() # 이미지를 바이트로 인코딩
        data.save(byte_stream, format='JPEG')
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


screen_thread = threading.Thread(target=temp)
screen_thread.start()

mouse_thread = threading.Thread(target=mouse_receive)
mouse_thread.start()

keyboard_thread = threading.Thread(target=keyboard_receive)
keyboard_thread.start()
