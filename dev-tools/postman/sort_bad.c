#include <stdio.h>
int main(){
    int n;
    if (scanf("%d", &n) != 1) return 1;
    char word[205];
    for (int i = 0; i < n; ++i) {
        if (scanf("%204s", word) != 1) return 1;
        printf("%s\n", word);
    }
    return 0;
}
