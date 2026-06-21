#include <winsock2.h>
#include <ws2tcpip.h>
#include <iostream>
#include <string>

#pragma comment(lib, "ws2_32.lib")

SOCKET client_socket = INVALID_SOCKET;

extern "C" {
    __declspec(dllexport) int connect_to_server(const char* ip, int port) {
        WSADATA wsa;
        if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) return 0;

        client_socket = socket(AF_INET, SOCK_STREAM, 0);
        if (client_socket == INVALID_SOCKET) return 0;

        sockaddr_in addr;
        addr.sin_family = AF_INET;
        addr.sin_port = htons(port);
        inet_pton(AF_INET, ip, &addr.sin_addr);

        if (connect(client_socket, (sockaddr*)&addr, sizeof(addr)) == SOCKET_ERROR) {
            closesocket(client_socket);
            client_socket = INVALID_SOCKET;
            return 0; 
        }
        return 1; 
    }

    __declspec(dllexport) void send_data(const char* msg) {
        if (client_socket != INVALID_SOCKET) {
            send(client_socket, msg, strlen(msg), 0);
        }
    }

    __declspec(dllexport) int receive_data(char* buffer, int buffer_size) {
        if (client_socket != INVALID_SOCKET) {
            // Trừ đi 1 để chừa khoảng trống cho ký tự \0
            int bytes = recv(client_socket, buffer, buffer_size - 1, 0);
            if (bytes > 0) {
                buffer[bytes] = '\0'; 
                return bytes;
            }
        }
        return -1; 
    }

    __declspec(dllexport) void disconnect() {
        if (client_socket != INVALID_SOCKET) {
            closesocket(client_socket);
            client_socket = INVALID_SOCKET;
        }
        WSACleanup();
    }
}