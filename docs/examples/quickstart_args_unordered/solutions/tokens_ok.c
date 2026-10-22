#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>

int main(int argc, char **argv) {
    if (argc < 2) return 1;
    int n = atoi(argv[1]);
    for (int i = 1; i <= n; i++) {
        pid_t pid = fork();
        if (pid < 0) return 1;
        if (pid == 0) {
            usleep((n - i) * 20000);
            printf("%d ", i);
            fflush(stdout);
            _exit(0);
        }
    }
    while (wait(NULL) > 0) {}
    printf("\n");
    return 0;
}
