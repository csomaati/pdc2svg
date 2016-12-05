import struct
import argparse
import logging
from collections import namedtuple

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('hu.csomaati.pebble.pdc2svg')


class Point(object):
    strct = struct.Struct('<2h')
    size = strct.size

    def __init__(self, bytestream, p_type):
        self.x, self.y = Point.strct.unpack(bytestream)

        if p_type == PebbleDrawCommand.TYPE_PRECISE_PATH:
            self.x = self.x / 8.0
            self.y = self.y / 8.0

        self.x += 0.5
        self.y += 0.5

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Point(x:{};y:{})".format(self.x, self.y)


class ViewBox(object):
    strct = struct.Struct('<2h')
    size = strct.size

    def __init__(self, bytestream):
        self.w, self.h = ViewBox.strct.unpack(bytestream)

    def __str__(self):
        return "ViewBox(w:{};h:{})".format(self.w, self.h)


class PebbleDrawCommand(object):
    strct = struct.Struct('<BBBBBhH')
    size = strct.size
    TYPE_PATH = 1
    TYPE_CIRCLE = 2
    TYPE_PRECISE_PATH = 3

    pdctype = {0: "Invalid", 1: "Path", 2: "Circle", 3: "Precise path"}
    pdcdynamic = {
        0b0000000000000000: "Closed path",
        0b0000000000000001: "Open path"
    }

    def __init__(self, f):
        (self.type, self.flags, self.strokecolor, self.strokewidth,
         self.fillcolor, self.path_radius, self.numberofpoints
         ) = PebbleDrawCommand.strct.unpack(f.read(PebbleDrawCommand.size))

        self.points = []

        for x in xrange(self.numberofpoints):
            new_point = Point(f.read(Point.size), self.type)
            self.points.append(new_point)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        typestr = PebbleDrawCommand.pdctype[self.type]
        dynamic_part = self.pdcdynamic[self.path_radius] if self.type in [
            1, 3
        ] else self.path_radius
        return "\n".join(
            ("\n\t\t\tType: {}".format(typestr),
             "\t\t\tFlags: {}".format(self.flags),
             "\t\t\tStroke color: #{:X}".format(self.strokecolor),
             "\t\t\tStroke width: {}".format(self.strokewidth),
             "\t\t\tFill color: #{:X}".format(self.fillcolor),
             "\t\t\tPath/Radius: {}".format(dynamic_part),
             "\t\t\tNumber of points: {}".format(self.numberofpoints),
             "\t\t\tPoints: {}".format(self.points)))


class PDCList(object):
    strct = struct.Struct('<H')
    size = strct.size

    def __init__(self, f):
        self.numberofcommands, = PDCList.strct.unpack(f.read(PDCList.size))

        self.commands = []

        for x in xrange(self.numberofcommands):
            new_command = PebbleDrawCommand(f)
            self.commands.append(new_command)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "\n".join(
            ("\n\t\tNumber of command: {}".format(self.numberofcommands),
             "\t\tCommands: {}".format(self.commands)))


class PDCFrame(object):
    strct = struct.Struct('<H')
    size = strct.size

    def __init__(self, f):
        self.duration, = PDCFrame.strct.unpack(f.read(PDCFrame.size))
        self.commandlist = PDCList(f)

    def __str__(self):
        return self.repr()

    def __repr__(self):
        return "\n\tPDCFrame(\n\t\tduration: {},\n\t\tcommandlist: {})".format(
            self.duration, self.commandlist)


class PDCImage(object):
    strct1 = struct.Struct('<BB')
    size = strct1.size + ViewBox.size

    def __init__(self, f):
        self.version, self.reserved = PDCImage.strct1.unpack(
            f.read(PDCImage.strct1.size))
        self.viewbox = ViewBox(f.read(ViewBox.size))

        self.commandlist = PDCList(f)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "\n".join(("PDCImage(", "\tVersion: {}".format(self.version),
                          "\tReserved: {0:#0x}".format(self.reserved),
                          "\tViewBox: {}".format(self.viewbox),
                          "\tCommandList: {})".format(self.commandlist)))


class PDCSequence(object):
    strct1 = struct.Struct('<BB')
    strct2 = struct.Struct('<HH')
    size = strct1.size + ViewBox.size + strct2.size

    def __init__(self, f):
        self.version, self.reserved = PDCSequence.strct1.unpack(
            f.read(PDCSequence.strct1.size))
        self.viewbox = ViewBox(f.read(ViewBox.size))
        self.playcount, self.framecount = PDCSequence.strct2.unpack(
            f.read(PDCSequence.strct2.size))

        self.framelist = []

        for x in xrange(self.framecount):
            new_frame = PDCFrame(f)
            self.framelist.append(new_frame)

    def __str__(self):
        playstring = self.playcount if self.playcount != 0xFFFF else "infinite"
        str = ("Version: {},\n".format(self.version),
               "Reserved: {},\n".format(self.reserved),
               "ViewBox: {},\n".format(self.viewbox),
               "PlayCount: {},\n".format(playstring),
               "FrameCount: {},\n".format(self.framecount),
               "FrameList: {}".format(self.framelist))
        str = ''.join(str)
        return str


def pdci2svg(pdc_file, svg_file):
    seq_size_fmt = '<i'
    seq_bytes = pdc_file.read(struct.calcsize(seq_size_fmt))
    seq_value, = struct.unpack(seq_size_fmt, seq_bytes)

    logger.info('Sequence size: %d', seq_value)

    pdc_image = PDCImage(pdc_file)
    logger.info("%s", pdc_image)


def pdcs2svg(pdc_file, svg_file):
    seq_size_fmt = '<i'
    seq_bytes = pdc_file.read(struct.calcsize(seq_size_fmt))
    seq_value, = struct.unpack(seq_size_fmt, seq_bytes)

    logger.info('Sequence size: %d', seq_value)

    pdc_sequence = PDCSequence(pdc_file)
    logger.info("%s", pdc_sequence)


def pdc2svg(pdc_file, svg_file):
    magic_fmt = '<4s'
    magic_bytes = pdc_file.read(4)
    magic_string, = struct.unpack(magic_fmt, magic_bytes)

    logger.info('Detected magic word: %s', magic_string)

    if magic_string == 'PDCI':
        pdci2svg(pdc_file, svg_file)
    elif magic_string == 'PDCS':
        pdcs2svg(pdc_file, svg_file)
    else:
        logger.error('Bad magic word. Can not decode this type of file')
        return


def main():
    parser = argparse.ArgumentParser(
        description='Convert pebble draw command files to svg')
    parser.add_argument('input', type=argparse.FileType('r'))
    parser.add_argument('output', type=argparse.FileType('w'))

    args = parser.parse_args()

    pdc2svg(args.input, args.output)


if __name__ == '__main__':
    main()
