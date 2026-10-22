#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>

#define N 4

int main(void) {
    for (int i = 1; i <= N; i++) {
        pid_t pid = fork();
        if (pid < 0) return 1;
        if (pid == 0) {
            usleep((N - i) * 20000); /* el fill 4 acaba primer: ordre de sortida invers */
            printf("fill %d\n", i);
            fflush(stdout);
            _exit(0);
        }
    }
    while (wait(NULL) > 0) {}
    return 0;
}
