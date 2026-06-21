#include <iostream>
#include <string>
#include <vector>
#include <thread>
#include <chrono>
#include <mutex>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <algorithm>
#include <ctime>
#include <iomanip>
#include <sstream>
#include "sqlite3.h" // Thư viện DB

using namespace std;
#pragma comment(lib, "ws2_32.lib")

const int BUFFER_SIZE = 2048;
const string DB_PATH = "../Database/chat.db";

struct ClientInfo {
    SOCKET socket;
    string username;
    bool isAuthenticated = false;
};

class ChatServer {
private:
    vector<ClientInfo*> clients;
    mutex clients_mutex;
    mutex db_mutex;
    SOCKET server_socket;
    sqlite3* db;

    string getTimestamp() {
        time_t now = time(0);
        tm *ltm = localtime(&now);
        char buffer[20];
        strftime(buffer, sizeof(buffer), "%H:%M:%S", ltm);
        return string(buffer);
    }

    void initDatabase() {
        if (sqlite3_open(DB_PATH.c_str(), &db) != SQLITE_OK) {
            cout << "[-] Loi mo Database: " << sqlite3_errmsg(db) << "\n";
            exit(1);
        }
        
        const char* sql = 
            "PRAGMA journal_mode=WAL;"
            "CREATE TABLE IF NOT EXISTS users ("
            "username TEXT PRIMARY KEY, password TEXT, status INTEGER, is_online INTEGER DEFAULT 0);"
            "CREATE TABLE IF NOT EXISTS history ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, message TEXT);";
            
        char* err = 0;
        sqlite3_exec(db, sql, 0, 0, &err);
        sqlite3_exec(db, "UPDATE users SET is_online = 0", 0, 0, 0);
    }

    void setOnlineStatus(const string& username, int status) {
        lock_guard<mutex> lock(db_mutex);
        string query = "UPDATE users SET is_online=? WHERE username=?";
        sqlite3_stmt* stmt;
        if (sqlite3_prepare_v2(db, query.c_str(), -1, &stmt, 0) == SQLITE_OK) {
            sqlite3_bind_int(stmt, 1, status);
            sqlite3_bind_text(stmt, 2, username.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
        }
    }

    void handleClient(ClientInfo* client) {
        char buffer[BUFFER_SIZE];
        vector<string> bad_words = {"domixi", "dmm", "nigga", "dit"};
        string recv_buffer = ""; // Dùng để cộng dồn byte TCP

        while (true) {
            // Nhận lượng byte chính xác để tránh tràn buffer
            int bytes = recv(client->socket, buffer, BUFFER_SIZE, 0);
            if (bytes <= 0) break;
            
            recv_buffer += string(buffer, bytes);
            size_t pos;
            
            // Xử lý từng thông điệp hoàn chỉnh dựa vào ký tự '\n'
            while ((pos = recv_buffer.find('\n')) != string::npos) {
                string data = recv_buffer.substr(0, pos);
                recv_buffer.erase(0, pos + 1);

                // --- XỬ LÝ ĐĂNG NHẬP ---
                if (data.find("LOGIN|") == 0) {
                    size_t p1 = data.find('|', 6);
                    if (p1 == string::npos) continue; 
                    
                    string u = data.substr(6, p1 - 6);
                    string p = data.substr(p1 + 1);
                    string response = "AUTH_FAIL\n"; // Gắn \n cho Client hiểu

                    {
                        lock_guard<mutex> lock(db_mutex);
                        string query = "SELECT status FROM users WHERE username=? AND password=?";
                        sqlite3_stmt* stmt;
                        
                        if (sqlite3_prepare_v2(db, query.c_str(), -1, &stmt, 0) == SQLITE_OK) {
                            sqlite3_bind_text(stmt, 1, u.c_str(), -1, SQLITE_TRANSIENT);
                            sqlite3_bind_text(stmt, 2, p.c_str(), -1, SQLITE_TRANSIENT);
                            
                            if (sqlite3_step(stmt) == SQLITE_ROW) {
                                int status = sqlite3_column_int(stmt, 0);
                                if (status == 1) {
                                    response = "AUTH_OK|domixi,dmm,nigga,dit\n";
                                    client->username = u;
                                    client->isAuthenticated = true;
                                } else {
                                    response = "AUTH_PENDING\n";
                                }
                            }
                            sqlite3_finalize(stmt);
                        }
                    }
                    
                    if (client->isAuthenticated) setOnlineStatus(u, 1);
                    send(client->socket, response.c_str(), response.length(), 0);
                }
                // --- XỬ LÝ ĐĂNG KÝ ---
                else if (data.find("REG|") == 0) {
                    size_t p1 = data.find('|', 4);
                    if (p1 == string::npos) continue;
                    
                    string u = data.substr(4, p1 - 4);
                    string p = data.substr(p1 + 1);
                    bool success = false;
                    
                    {
                        lock_guard<mutex> lock(db_mutex);
                        string query = "INSERT INTO users (username, password, status, is_online) VALUES (?, ?, 0, 0)";
                        sqlite3_stmt* stmt;
                        if (sqlite3_prepare_v2(db, query.c_str(), -1, &stmt, 0) == SQLITE_OK) {
                            sqlite3_bind_text(stmt, 1, u.c_str(), -1, SQLITE_TRANSIENT);
                            sqlite3_bind_text(stmt, 2, p.c_str(), -1, SQLITE_TRANSIENT);
                            if (sqlite3_step(stmt) == SQLITE_DONE) {
                                success = true;
                            }
                            sqlite3_finalize(stmt);
                        }
                    }
                    
                    string response = success ? "REG_OK\n" : "REG_FAIL\n";
                    send(client->socket, response.c_str(), response.length(), 0);
                }
                // --- XỬ LÝ CHAT ---
                else if (data.find("CHAT|") == 0 && client->isAuthenticated) {
                    string msg_content = data.substr(5);
                    
                    for (const string& word : bad_words) {
                        size_t word_pos = 0;
                        string stars(word.length(), '*');
                        while ((word_pos = msg_content.find(word, word_pos)) != string::npos) {
                            msg_content.replace(word_pos, word.length(), stars);
                            word_pos += stars.length();
                        }
                    }

                    string ts = getTimestamp();
                    string fullMsg = "[" + ts + "] " + client->username + ": " + msg_content + "\n"; // Đã gắn \n
                    auto start_time = chrono::high_resolution_clock::now();
                    {
                        lock_guard<mutex> lock(db_mutex);
                        string query = "INSERT INTO history (timestamp, message) VALUES (?, ?)";
                        sqlite3_stmt* stmt;
                        
                        if (sqlite3_prepare_v2(db, query.c_str(), -1, &stmt, 0) == SQLITE_OK) {
                            string full_log = client->username + ": " + msg_content;
                            sqlite3_bind_text(stmt, 1, ts.c_str(), -1, SQLITE_TRANSIENT);
                            sqlite3_bind_text(stmt, 2, full_log.c_str(), -1, SQLITE_TRANSIENT);
                            sqlite3_step(stmt);
                            sqlite3_finalize(stmt);
                        }
                    }
                    auto end_time = chrono::high_resolution_clock::now();
                    auto duration = chrono::duration_cast<chrono::microseconds>(end_time - start_time).count();
                    cout << "[METRIC] Thoi gian luu DB: " << duration << " micro-giay (" << duration/1000.0 << " ms)\n";
                    lock_guard<mutex> lock(clients_mutex);
                    for (auto c : clients) {
                        if (c->isAuthenticated && c != client) {
                            send(c->socket, fullMsg.c_str(), (int)fullMsg.length(), 0);
                        }
                    }
                    string ack = "ACK\n";
                    send(client->socket, ack.c_str(), ack.length(), 0);
                }
            }
        }

        if (client->isAuthenticated) {
            setOnlineStatus(client->username, 0);
        }
        closesocket(client->socket);      
        lock_guard<mutex> lock(clients_mutex);
        clients.erase(remove(clients.begin(), clients.end(), client), clients.end());
        delete client;
    }

public:
    void start(int port) {
        initDatabase();
        WSADATA wsa; 
        WSAStartup(MAKEWORD(2, 2), &wsa);
        server_socket = socket(AF_INET, SOCK_STREAM, 0);
        sockaddr_in addr;
        addr.sin_family = AF_INET;
        addr.sin_port = htons(port);
        addr.sin_addr.s_addr = INADDR_ANY;       
        bind(server_socket, (sockaddr*)&addr, sizeof(addr));
        listen(server_socket, SOMAXCONN);
        
        cout << "=== SERVER START TAI PORT " << port << " ===\n";
        cout << "[+] Database SQLite da ket noi thanh cong.\n";
        cout << "[+] Server dang lang nghe. (Chay admin.py de quan tri)\n";

        while (true) {
            SOCKET incoming = accept(server_socket, 0, 0);
            if (incoming == INVALID_SOCKET) continue;
            ClientInfo* c = new ClientInfo();
            c->socket = incoming;
            { 
                lock_guard<mutex> lock(clients_mutex); 
                clients.push_back(c); 
            }           
            thread(&ChatServer::handleClient, this, c).detach();
        }
    }
};

int main() {
    ChatServer server;
    server.start(9999);
    return 0;
}