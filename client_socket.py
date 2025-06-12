import socket
import pyautogui
import io

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print("write server adress")
server_address = input()

server_address_port = (server_address,8843)

client_socket.connect(server_address_port)
print("connected")

width, height = pyautogui.size() # 화면 픽셀

send_width = width.to_bytes(4, byteorder="big")
send_height = height.to_bytes(4, byteorder="big")

send_scale = send_width + "s".encode("utf-8") + send_height # 화면 비율 인코딩 s는 구분자

client_socket.send(send_scale) # 화면 비율 보내기

while True:
    data=pyautogui.screenshot() # 화면 캡쳐후 image객체로 생성

    byte_stream = io.BytesIO() # 이미지를 바이트로 인코딩
    data.save(byte_stream, format='PNG')
    send_img = byte_stream.getvalue()

    how_bytes_long_str = str(len(send_img)) # 이미지 바이트 길이 구하기
    how_bytes_long_str = str(len(how_bytes_long_str) + int(how_bytes_long_str) + 1)+"l" # l는 구분자

    send_long = how_bytes_long_str.encode("utf-8") # 길이를 바이트로 인코딩

    send_data = send_long+send_img # 길이와 이미지 결합
    client_socket.send(send_data) # (바이트 길이 + 이미지) 보내기