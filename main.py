u'''
Working theory:

read in metadata
for the shape:
    is it clockwise? 
        correct direction
    find shape centre
    offset coordinates
    are there corner rads?
        adjust corner radius
        add corner coordinates
calculate pass depths
produce gcode
tidy gcode
write to output file
'''
from __future__ import division
from __future__ import absolute_import
from __future__ import with_statement
from io import open

class Shape(object):
    def __init__(self, filename):
        self.datum_x = None
        self.datum_y = None
        self.coordinates = []  # Initialize coordinates as an empty list
        self.shape = None
        self.offset = None
        self.corner_radius = None
        self.tool_diameter = None
        self.pass_depth = None
        self.material_thickness = None
        self.bottom_offset = None
        self.feedrate = None
        self.plungerate = None
        self.spindle_speed = None
        self.is_climb = False
        
        self.tabs = False
        self.read_data_from_file(filename)

    def read_data_from_file(self, filename):
        try:
            with open(filename, u'r') as file:
                lines = file.readlines()

            for line in lines:
                key, value = line.lower().strip().split(u":")
                key = key.strip()
                value = value.strip()
                if key == u"datum x":
                    self.datum_x = float(value)
                elif key == u"datum y":
                    self.datum_y = float(value)
                elif key == u"shape":
                    self.shape = value
                elif key == u"corner radius":
                    self.corner_radius = float(value)
                elif key == u"offset":
                        if value == u"none":
                            self.offset = None
                        else:
                            self.offset = value
                elif key == u"tool diameter":
                    self.tool_diameter = float(value)
                elif key == u"pass depth":
                    self.pass_depth = float(value)
                elif key == u"material thickness":
                    self.material_thickness = float(value)
                elif key == u"bottom offset":
                    self.bottom_offset = float(value)
                elif key == u"feedrate":
                    self.feedrate = float(value)
                elif key == u"plungerate":
                    self.plungerate = float(value)
                elif key == u"spindle speed":
                    self.spindle_speed = int(value)
                elif key == u"cut direction":
                    if value == u"climb":
                        self.is_climb = True
                elif key == u"tabs":
                    if value == u"true":
                        self.tabs = True
                elif key == u"finish stepdown":
                    self.finish_stepdown = float(value)
                elif key == u"finish passes":
                    self.finish_passes = int(value)
                elif key == u"finish stepover":
                    self.finish_stepover = float(value)
                elif key == u"point":
                    # Split the coordinate string by "," to get the x and y values
                    x, y = value.split(u",")
                    x = float(x)
                    y = float(y)
                    self.coordinates.append((x, y))
                else:
                    print ("Unknown key: %s" % key)

        except IOError:
            print ("File '%s' not found" % filename)

    def __str__(self):
        coordinates_str = u", ".join(["(%s, %s)" % (x, y) for x, y in self.coordinates])
        return "Datum X: %s, Datum Y: %s, Coordinates: %s, Shape: %s, Offset: %s, Corner radius: %s, Tool diameter: %s, " \
               "Pass depth: %s, Material thickness: %s, " \
               "Bottom offset: %s, Feedrate: %s, Plungerate: %s, Spindle speed: %s, Is climb: %s, Tabs: %s" % (self.datum_x, self.datum_y, coordinates_str, self.shape, self.offset, self.corner_radius, self.tool_diameter,
                self.pass_depth, self.material_thickness, self.bottom_offset, self.feedrate, self.plungerate, self.spindle_speed, self.is_climb, self.tabs)

#Adjust corner radius depending on the offset type (in, on, outside of line)
def offset_corner_radius(corner_radius, offset_type, tool_diameter):
    if offset_type == u"inside":
        return corner_radius - tool_diameter
    elif offset_type == u"outside":
        return corner_radius + tool_diameter
    elif offset_type == None:
        return corner_radius
    else: 
        raise  Exception(u"Unknown offset type. Please specify 'inside', 'outside' or 'none'.")

#Find the shape centre coordinates
def find_centre(coordinates, x_offset, y_offset):
    x_sum = 0
    y_sum = 0
    for x, y in coordinates:
        x_sum += x + x_offset
        y_sum += y + y_offset
    centre_x = x_sum / len(coordinates)
    centre_y = y_sum / len(coordinates)

    return centre_x, centre_y

#Check if a corner radius is present (and not tiny)
def find_corner_rads(radius):
    if radius > 0.09:
        return True
    else:
        return False

#Determine shape point direction
def is_clockwise(coordinates):
    total = 0
    for i in xrange(len(coordinates)):
        x1, y1 = coordinates[i]
        x2, y2 = coordinates[(i + 1) % len(coordinates)]  # Handle the wraparound at the end
        total += (x2 - x1) * (y2 + y1)
    
    if total > 0:
        return False
    elif total < 0:
        return True

#Reverse coordinates if need to be clockwise
def correct_orientation(coordinates, clockwise):
    if clockwise:
        return coordinates[::-1]
    else:
        return coordinates

#Take in corner coordinates and return coordinates for arcs
def add_corner_coordinates(coordinates, shape_centre, corner_radius):
    new_coordinates = []
    for coordinate in coordinates:
        #Bottom left
        if coordinate[x] < shape_centre[x] and coordinate[y] < shape_centre[y]: 
            rad_point_1 = coordinate[x] + corner_radius, coordinate[y]
            rad_point_2 = coordinate[x], coordinate[y] + corner_radius
        #Top left
        elif coordinate[x] < shape_centre[x] and coordinate[y] > shape_centre[y]:
            rad_point_1 = coordinate[x], coordinate[y] - corner_radius
            rad_point_2 = coordinate[x] + corner_radius, coordinate[y]
        #Top right
        elif coordinate[x] > shape_centre[x] and coordinate[y] > shape_centre[y]:
            rad_point_1 = coordinate[x] - corner_radius, coordinate[y]
            rad_point_2 = coordinate[x], coordinate[y] - corner_radius
        #Bottom right
        elif coordinate[x] > shape_centre[x] and coordinate[y] < shape_centre[y]:
            rad_point_1 = coordinate[x], coordinate[y] + corner_radius
            rad_point_2 = coordinate[x] - corner_radius, coordinate[y]
        new_coordinates.append(rad_point_1)
        new_coordinates.append(rad_point_2)
    return new_coordinates 

#Calculate the difference in corner radius depending on offset type
def calculate_corner_radius_offset(offset_type, tool_diamter):
    tool_radius = tool_diamter / 2
    if offset_type == u"inside":
        offset_for_rads = -1 * tool_radius
    elif offset_type == u"outside":
        offset_for_rads = tool_radius
    else:
        offset_for_rads = 0
    return offset_for_rads

#Apply transformation for inside and outside line cutting
def apply_offset(coordinates, offset_type, tool_diameter, shape_centre):
    adjusted_coordinates = []
    if offset_type != None:
        tool_radius = tool_diameter / 2
        #x_offset = tool_radius 
        #y_offset = tool_radius 
        for coordinate in coordinates:

            if offset_type == u"inside":

                if coordinate[x] > shape_centre[x]: #RHS
                    x_offset = -1 * tool_radius #Move to the left
                else: #LHS
                    x_offset = tool_radius #Move to the right
                    
                if coordinate[y] > shape_centre[y]: #Top
                    y_offset = -1 * tool_radius #Move down
                else: #Bottom
                    y_offset = tool_radius #Move up

            elif offset_type == u"outside":

                if coordinate[x] < shape_centre[x]: #LHS
                    x_offset = -1 * tool_radius #Move to the left
                else:#RHS
                    x_offset = tool_radius #Move to the right

                if coordinate[y] < shape_centre[y]: #Bottom
                    y_offset = -1 * tool_radius #Move down
                else: #Top
                    y_offset = tool_radius #Move up
            new_coordinate = coordinate[x] + x_offset, coordinate[y] + y_offset 
            adjusted_coordinates.append(new_coordinate)
    else:
        adjusted_coordinates = coordinates

    return  adjusted_coordinates

    pass

#Produce a list of cut depths based on total depth and pass depth
def calculate_pass_depths(total_cut_depth, pass_depth):
    pass_depths = []
    current_depth = pass_depth
    while current_depth < total_cut_depth:
        pass_depths.append(current_depth)
        current_depth += pass_depth
    try:
        if max(pass_depths) < total_cut_depth:
            pass_depths.append(total_cut_depth)
    except:
        pass_depths = [total_cut_depth]
    return pass_depths

#Determine if the cut direction should be clockwise or not
def determine_cut_direction_clockwise(offset_type, climb):
    if climb and offset_type == u"outside" or not(climb) and offset_type == u"inside":
        return True
    else:
        return False

#For use when reordering gcode instructions
def swap_lines_after_keyword(input_list, keyword):
    i = 0
    while i < len(input_list):
        if keyword.lower() in input_list[i].lower():
            # Check if there are at least two lines after the keyword
            if i + 2 < len(input_list):
                # Swap the lines
                input_list[i + 1], input_list[i + 2] = input_list[i + 2], input_list[i + 1]
            i += 3  # Move to the next keyword (assuming each occurrence is separated by 2 lines)
        else:
            i += 1
    return input_list

#For use when reordering gcode instructions
def replace_after_keyword(input_list, keyword, replacement):
    for i in xrange(len(input_list) - 1):
        if keyword.lower() in input_list[i].lower():
            if i + 1 < len(input_list):
                # Replace the first two letters of the line that follows the keyword
                input_list[i + 1] = replacement + input_list[i + 1][2:]
    return input_list

def cut_rectangle(coordinates, datum_x, datum_y, offset, tool_diameter, is_climb, corner_radius, pass_depth, feedrate, plungerate, total_cut_depth, z_safe_distance):
        # Ensure coordinates are all in clockwise order
        coordinates = correct_orientation(coordinates, is_clockwise(coordinates))

        # Find shape centre for further calcs
        shape_centre = find_centre(coordinates, datum_x, datum_y)

        # Apply offset for toolpath (inside, on, outside the line cutting)
        offset_coordinates = apply_offset(coordinates, offset, tool_diameter, shape_centre)

        clockwise_cutting = determine_cut_direction_clockwise(offset, is_climb)

        # Add corner coordinates if necessary
        radii_present = find_corner_rads(corner_radius)
        final_coordinates = offset_coordinates
        if radii_present:
            adjusted_corner_radius = corner_radius + calculate_corner_radius_offset(offset, tool_diameter)
            if adjusted_corner_radius > 0:
                final_coordinates = add_corner_coordinates(offset_coordinates, shape_centre, adjusted_corner_radius)
            else:
                radii_present = False
            

        pass_depths = calculate_pass_depths(total_cut_depth, pass_depth)

        # Time to make some gcode :)
        if clockwise_cutting:
            arc_instruction = u"G2"
        else:
            final_coordinates = correct_orientation(final_coordinates, True)
            arc_instruction = u"G3"

        cutting_lines = []

        for depth in pass_depths:
            gcode_instruction = "(Offset: %s)\n(New pass)\n" % offset
            cutting_lines.append(gcode_instruction)
            cutting_lines.append("G1 Z-%s F%s\n" % (depth, plungerate))
            # Cut the shape
            if not radii_present:
                # Logic for straight lines only
                for coordinate in final_coordinates:
                    second_line = 1 == final_coordinates.index(coordinate)
                    gcode_instruction = "G1 X%s Y%s %s\n" % (coordinate[0] + datum_x, coordinate[1] + datum_y, 'F%s' % feedrate if second_line else '')
                    cutting_lines.append(gcode_instruction)
            else:
                # Logic for when corner rads are present
                arc_flag = True
                for coordinate in final_coordinates[:-1]:
                    second_line = 1 == final_coordinates.index(coordinate)
                    gcode_instruction = "G1 X%s Y%s %s\n" % (coordinate[0] + datum_x, coordinate[1] + datum_y, 'F%s' % feedrate if second_line else '')
                    if arc_flag:
                        gcode_instruction = "G1 X%s Y%s\n" % (coordinate[0] + datum_x, coordinate[1] + datum_y)
                    else:
                        gcode_instruction = "%s X%s Y%s R%s\n" % (arc_instruction, coordinate[0] + datum_x, coordinate[1] + datum_y, adjusted_corner_radius)
                    arc_flag = not arc_flag
                    cutting_lines.append(gcode_instruction)
            cutting_lines.append("G1 Z%d F%d\n\n" % (z_safe_distance, plungerate))

        # Correct gcode order
        cutting_lines = swap_lines_after_keyword(cutting_lines, u"New pass")
        # Speed up first XY move
        cutting_lines = replace_after_keyword(cutting_lines, u"New pass", u"G0")

        return cutting_lines

# Initial definitions
x = 0  # Identifier for use in arrays
y = 1  # Identifier for use in arrays
filename = u"basic_rectangle.ymd"
output_file = filename[:filename.find(u".")] + u".nc"
safe_start_position = u"X0 Y0 Z10"
z_safe_distance = 5
cutting_lines = []
pass_depths = []
stepovers = [0]
radii_present = None

shape_data = Shape(filename)

if shape_data.shape == u"rectangle":
    if len(shape_data.coordinates) != 4:
        raise Exception(u"Sir, rectangles have 4 sides, not %d" % len(shape_data.coordinates))

    # Calculated parameters
    total_cut_depth = shape_data.material_thickness - shape_data.bottom_offset

    # Add first point to end of coordinate list to complete the contour
    coordinates = shape_data.coordinates
    coordinates.append(coordinates[0])

    # Create a list of stepovers to add finishing passes
    finish_passes = shape_data.finish_passes
    finish_stepover = shape_data.finish_stepover
    if finish_passes > 0:
        stepovers = [finish_stepover * (finish_passes - i) for i in range(finish_passes)]
        stepovers.append(0)

    # Produce instructions for each complete rectangle
    for stepover in stepovers:
        effective_tool_diameter = shape_data.tool_diameter + (stepover * 2)
        pass_depth = shape_data.finish_stepdown if stepover != max(stepovers) else shape_data.pass_depth
        rectangle = cut_rectangle(coordinates,
                                  shape_data.datum_x,
                                  shape_data.datum_y,
                                  shape_data.offset,
                                  effective_tool_diameter,
                                  shape_data.is_climb,
                                  shape_data.corner_radius,
                                  pass_depth,
                                  shape_data.feedrate,
                                  shape_data.plungerate,
                                  total_cut_depth,
                                  z_safe_distance)

        cutting_lines += rectangle

else:
    raise Exception("Shape type: %s not supported" % shape_data.shape)

# GCODE FILE STRUCTURE
output = "(%s)\nM3 S%d\nG0 %s\n\n%s\n(End)\nG0 Z%d\nM5\n" % (
    output_file, shape_data.spindle_speed, safe_start_position, ''.join(cutting_lines), z_safe_distance)

with open(output_file, 'w+') as out_file:
    out_file.writelines(output)
    print ("%s written" % output_file)

