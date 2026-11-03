import sys
import math

# Auto-generated code below aims at helping you parse
# the standard input according to the problem statement.

house_count = int(input())
for i in range(house_count):
    house_id, house_x, house_y = [int(j) for j in input().split()]

# game loop
while True:
    my_score, opponent_score = [int(i) for i in input().split()]
    for i in range(house_count):
        house_id, my_units, opponent_units = [int(j) for j in input().split()]
    path_count = int(input())
    for i in range(path_count):
        house1, house2 = [int(j) for j in input().split()]
    triangle_count = int(input())
    for i in range(triangle_count):
        inputs = input().split()
        house1 = int(inputs[0])
        house2 = int(inputs[1])
        house3 = int(inputs[2])
        owner = int(inputs[3])
        me_can_capture = inputs[4] != "0"
        opponent_can_capture = inputs[5] != "0"
    linkable_count = int(input())
    for i in range(linkable_count):
        house1, house2 = [int(j) for j in input().split()]

    # Write an action using print
    # To debug: print("Debug messages...", file=sys.stderr, flush=True)

    print("MOVE 3 17 1")
