#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    if (argc < 2) return 1;
    int n = atoi(argv[1]);
    int x;
    if (scanf("%d", &x) != 1) return 1;
    for (int i = 1; i <= n; i++) printf("%d\n", x * i);
    return 0;
}
