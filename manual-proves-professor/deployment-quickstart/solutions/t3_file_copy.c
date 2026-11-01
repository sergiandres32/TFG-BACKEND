#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc != 3) return 1;

    int input_fd = open(argv[1], O_RDONLY);
    if (input_fd < 0) return 2;
    int output_fd = open(argv[2], O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (output_fd < 0) {
        close(input_fd);
        return 3;
    }

    char buffer[128];
    ssize_t count;
    long total = 0;
    while ((count = read(input_fd, buffer, sizeof(buffer))) > 0) {
        ssize_t offset = 0;
        while (offset < count) {
            ssize_t written = write(output_fd, buffer + offset, (size_t)(count - offset));
            if (written <= 0) {
                close(input_fd);
                close(output_fd);
                return 4;
            }
            offset += written;
        }
        total += count;
    }

    if (count < 0 || close(input_fd) < 0 || close(output_fd) < 0) return 5;
    char message[64];
    int message_length = snprintf(message, sizeof(message), "copied %ld bytes\n", total);
    if (message_length < 0 || write(STDOUT_FILENO, message, (size_t)message_length) != message_length) return 6;
    return 0;
}
