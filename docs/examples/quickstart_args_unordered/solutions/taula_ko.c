#include <stdio.h>

/* WA: ignora argv i usa N=2 fix */
int main(void) {
    int x;
    if (scanf("%d", &x) != 1) return 1;
    for (int i = 1; i <= 2; i++) printf("%d\n", x * i);
    return 0;
}
