#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

int main(void) {
    int count_fd = open("count.txt", O_RDONLY);
    if (count_fd < 0) return 1;
    char count_text[32] = {0};
    ssize_t count_length = read(count_fd, count_text, sizeof(count_text) - 1);
    if (count_length <= 0 || close(count_fd) < 0) return 2;
    int child_count = atoi(count_text);
    if (child_count < 1 || child_count > 8) return 3;

    int descriptors[2];
    if (pipe(descriptors) < 0) return 4;
    for (int child_index = 1; child_index <= child_count; child_index++) {
        pid_t child = fork();
        if (child < 0) return 5;
        if (child == 0) {
            close(descriptors[0]);
            char token[16];
            int token_length = snprintf(token, sizeof(token), "%d ", child_index);
            if (token_length < 0 || write(descriptors[1], token, (size_t)token_length) != token_length) _exit(6);
            close(descriptors[1]);
            _exit(0);
        }
    }

    close(descriptors[1]);
    char buffer[64];
    ssize_t bytes_read;
    while ((bytes_read = read(descriptors[0], buffer, sizeof(buffer))) > 0) {
        ssize_t offset = 0;
        while (offset < bytes_read) {
            ssize_t written = write(STDOUT_FILENO, buffer + offset, (size_t)(bytes_read - offset));
            if (written <= 0) return 7;
            offset += written;
        }
    }
    if (bytes_read < 0 || close(descriptors[0]) < 0) return 8;
    if (write(STDOUT_FILENO, "\n", 1) != 1) return 9;

    for (int child_index = 0; child_index < child_count; child_index++) {
        int status;
        if (wait(&status) < 0 || !WIFEXITED(status) || WEXITSTATUS(status) != 0) return 10;
    }
    return 0;
}
