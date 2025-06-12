import socket
from PIL import Image
import io
import pyautogui
import sys
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1' # pygame 출력 가리
import pygame

my_ip = socket.gethostbyname(socket.gethostname()) # 내 아이피

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_address_port = (my_ip,8843)

server_socket.bind(server_address_port)

server_socket.listen()
print(my_ip+' socket waiting')
client_socket, client_address = server_socket.accept()
print("connected from " + client_address[0]) 

my_width, my_height = pyautogui.size() # 화면 픽셀

receive_scale = client_socket.recv(1024) # 클라이언트 화면 너비, 높이 확인용

receive_width = int.from_bytes(receive_scale[:receive_scale.index(b's')], byteorder="big")
receive_height = int.from_bytes(receive_scale[receive_scale.index(b's')+1:len(receive_scale)], byteorder="big")

if receive_height*my_width/receive_width<=my_height: # 비율 최적화
    width_scale = my_width
    height_scale = receive_height*my_width/receive_width
else:
    width_scale = receive_width*my_height/receive_height
    height_scale = my_height

# width_scale *= 6/7
# height_scale *= 6/7

screen = pygame.display.set_mode((width_scale, height_scale))
pygame.display.set_caption("screen sharing")
clock = pygame.time.Clock()
pygame.init()

fps=30
while 1:
    clock.tick(fps)

    for event in pygame.event.get():
        if event.type==pygame.QUIT:
            pygame.quit()
            server_socket.close()
            sys.exit()

    receive_data = client_socket.recv(1024) # 길이 확인용으로 받기

    real_long = int(receive_data[:receive_data.index(b'l')].decode("utf-8")) # 바이트 길이 추출

    while len(receive_data)!=real_long: # 데이터 길이 만큼 받기
        receive_data+=client_socket.recv(real_long-len(receive_data)) 

    receive_img = receive_data[receive_data.index(b'l')+1:real_long] # 데이터에서 이미지 추출

    io_data = io.BytesIO(receive_img) # 이미지 디코딩
    PIL_img = Image.open(io_data)
    
    pygame_img = pygame.image.fromstring(PIL_img.tobytes(), PIL_img.size, PIL_img.mode) # PIL이미지 pygame으로 변환
    show_img = pygame.transform.scale(pygame_img, (width_scale, height_scale))
    
    screen.blit(show_img, (0,0))
    pygame.display.update()