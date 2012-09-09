#!/usr/bin/python
# -*- coding: utf-8 -*-

#
# Licensed under the GNU General Public License Version 2 or later
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# Copyright (C) 2012
#    Francisco Dos Santos <f.dos.santos@free.fr>

import os, sys
import re
import psycopg2
from osgeo import ogr, osr
from shapeu import ShapeUtil
import caop_config

#
# Definitions
#
regexp = re.compile("([- ()/])")   # Separators in name
preposition = (
    "De", "Do", "Da", "Dos", "Das",
    "E", "A", "O", "Os", "D'", "Ao", u'\xC0'   # A with grave accent
)


#
# Functions
#

def convertname(name):
    """
    Convert and normalize name from an ISO8859 string to an UTF8 string.
    Earch word in the name are capitalized except some portuguese preposition
    """

    name = name.decode("ISO8859")
    tokens = regexp.split(name)   # List of word, separator, ...

    # Finish the split job, we need a list of pair elements (for loop below)
    # depends on if the string end with a separator or not, there is one
    # element we can discard or there is one element missing
    if tokens[-1]:
        tokens.append("")   # ends with word and no separator
    else:
        del tokens[-1]      # last word empty, ends with a separator

    # First letter in upper case except some known words after first word
    for i in xrange(0, len(tokens), 2):
        tok = tokens[i].capitalize()
        if i > 0:
            if tok in preposition:
                tok = tok.lower()
        tokens[i] = tok

        # Special case: eat the space following a d' preposition
        if tok == "d'" and tokens[i+1] == " ":
            tokens[i+1] = ""

    # Return string in UTF8
    name = ''.join(tokens)
    return name.encode("UTF8")


def read_CAOP(filename, shapeu):
    """
    Read the shapefile and build the AdminEnt object for each administrative
    entity.

    We expect only 1 layer of type polygon, coordinate reprojected to WGS84,
    string attribute converted to UTF8.
    """

    shapefile = ogr.Open(filename)
    layer = shapefile.GetLayer(0)
    layerDef = layer.GetLayerDefn()

    # Verify field and geometry type
    for field in ( "DICOFRE", "MUNICIPIO", "FREGUESIA" ):
        if layerDef.GetFieldIndex(field) == -1:
            raise Exception("Field '%s' not found" % field)
    if (layerDef.GetFieldIndex("DISTRITO") == -1
      and layerDef.GetFieldIndex("ILHA") == -1):
        raise Exception("Field 'DISTRITO' or 'ILHA' not found")
    if layerDef.GetGeomType() != ogr.wkbPolygon:
        raise Exception("Not a POLYGON file")

    # Reproject on the fly
    srcSpatialRef = layer.GetSpatialRef()
    dstSpatialRef = osr.SpatialReference()
    dstSpatialRef.SetWellKnownGeogCS('WGS84')
    transform = osr.CoordinateTransformation(srcSpatialRef, dstSpatialRef)

    # Read each polygon and build the connection arrays (point, segment, line)
    for featnum in xrange(layer.GetFeatureCount()):
        feature = layer.GetFeature(featnum)
        geometry  = feature.GetGeometryRef()
        newgeometry = geometry.Clone()
        newgeometry.Transform(transform)

        # Outer Ring (1) followed by Inner Rings (n-1)
        # we create all segments for each ring to find the topology ...
        for i in xrange(newgeometry.GetGeometryCount()):
            ring = newgeometry.GetGeometryRef(i)
            lon1, lat1 = ring.GetPoint_2D(0)
            for pnt in xrange(1, ring.GetPointCount()):
                lon2, lat2 = ring.GetPoint_2D(pnt)
                shapeu.makeSegment(lon1, lat1, lon2, lat2)
                lon1, lat1 = lon2, lat2


def admin_CAOP(filename, shapeu, admins):
    """
    Reread the shapefile and build each administrative entity.

    We expect only 1 layer of type polygon, coordinate reprojected to WGS84,
    string attribute converted to UTF8.
    """

    shapefile = ogr.Open(filename)
    layer = shapefile.GetLayer(0)
    layerDef = layer.GetLayerDefn()

    # Detect if we are dealing with Portugal or the autonomous regions
    if layerDef.GetFieldIndex("DISTRITO") != -1:
        isregion = False
        toplevel = "DISTRITO"
    elif layerDef.GetFieldIndex("ILHA") != -1:
        isregion = True
        toplevel = "ILHA"

    # Reproject on the fly
    srcSpatialRef = layer.GetSpatialRef()
    dstSpatialRef = osr.SpatialReference()
    dstSpatialRef.SetWellKnownGeogCS('WGS84')
    transform = osr.CoordinateTransformation(srcSpatialRef, dstSpatialRef)

    # Reread each polygon and create the right administrative area
    for featnum in xrange(layer.GetFeatureCount()):
        feature = layer.GetFeature(featnum)
        geometry  = feature.GetGeometryRef()
        newgeometry = geometry.Clone()
        newgeometry.Transform(transform)
        dicofre   = feature.GetField("DICOFRE")
        distrito  = convertname(feature.GetField(toplevel))
        municipio = convertname(feature.GetField("MUNICIPIO"))
        freguesia = convertname(feature.GetField("FREGUESIA"))

        # Distrito or Region
        if isregion:
            dicofre1  = dicofre[0:1]
            if not admins.has_key(dicofre1):
                # Extract archipelago name from island name
                m = re.search("\(([^)]+)\)", distrito)
                if m:
                    distrito = m.group(1)
                admins[dicofre1] = { "name" : distrito,
                                     "level" : 4,
                                     "inner" : set(),
                                     "outer" : set()
                                   }
        else:
            dicofre1  = dicofre[0:2]
            if not admins.has_key(dicofre1):
                admins[dicofre1] = { "name" : distrito,
                                     "level" : 6,
                                     "inner" : set(),
                                     "outer" : set()
                                   }

        # Municipio
        dicofre2  = dicofre[0:4]
        if not admins.has_key(dicofre2):
            admins[dicofre2] = { "name" : municipio,
                                 "level" : 7,
                                 "inner" : set(),
                                 "outer" : set()
                               }

        # Freguesia
        if not admins.has_key(dicofre):
            admins[dicofre]  = { "name" : freguesia,
                                 "level" : 8,
                                 "inner" : set(),
                                 "outer" : set()
                               }

        # Build sets of lineid, 1 for outer ring and 1 for inner rings
        outer = set()
        inner = set()
        currentset = outer
        for i in xrange(newgeometry.GetGeometryCount()):
            ring = newgeometry.GetGeometryRef(i)
            pntinring = []
            for pnt in xrange(ring.GetPointCount()):
                lon, lat = ring.GetPoint_2D(pnt)
                pointid = shapeu.getPoint(lon, lat)
                if pointid is not None:
                    pntinring.append(pointid)

            if pntinring[0] != pntinring[-1]:
                # Simplification have broken the ring,
                # starting point was in the middle of a simplified line
                pntinring.append(pntinring[0])

            for pnt in xrange(1, len(pntinring)):
                if pntinring[pnt-1] ==  pntinring[pnt]:
                    # If 2 coordinates after rounding give the same point id
                    # (safety measure, normaly doesn't happen)
                    continue
                segment = shapeu.getSegment(pntinring[pnt-1], pntinring[pnt])
                currentset.add(shapeu.getLine(segment))

            currentset = inner

        # Update each administrative level
        admins[dicofre]["outer"].update(outer)
        admins[dicofre]["inner"].update(inner)

        admins[dicofre2]["outer"].symmetric_difference_update(outer)
        admins[dicofre2]["outer"].symmetric_difference_update(inner)

        admins[dicofre1]["outer"].symmetric_difference_update(outer)
        admins[dicofre1]["outer"].symmetric_difference_update(inner)


def findclosedrings(lines, shapeu, closedrings):
    """
    Group lines in closed rings.
    From a list of unordered lineid construct a list of closed rings,
    each closed rings is a list of ordered lineid.
    Return 0 if all lines are correctly grouped in closed rings.
    """

    lineconnect = []
    openrings = []
    for lineid in lines:
        pointid1, pointid2 = shapeu.getLineEnds(lineid)
        if pointid1 == pointid2:
            # line is a closed loop per itself
            closedrings.append([ lineid ])
            continue
        try:
            seg1 = lineconnect.index(pointid1)
            # link on pointid1
            ring = openrings[seg1/2]
            try:
                seg2 = lineconnect.index(pointid2)
                if seg1^1 == seg2:
                    # the missing piece to close the ring
                    ring.append(lineid)
                    closedrings.append(ring)
                    seg1 = seg1 & ~1
                    del openrings[seg1/2]
                    del lineconnect[seg1]
                    del lineconnect[seg1]
                else:
                    # merge 2 pieces together, find which ends to connect to
                    ring2 = openrings[seg2/2]
                    if seg1 & 1 == 0:
                        if seg2 & 1 == 0:
                            # new piece links start of both rings
                            ring.reverse()
                            ring.append(lineid)
                            ring.extend(ring2)
                            lineconnect[seg1] = lineconnect[seg1+1]
                            lineconnect[seg1+1] = lineconnect[seg2+1]
                        else:
                            # new piece links end of 2nd ring with start of 1st
                            ring2.append(lineid)
                            ring2.extend(ring)
                            seg2 = seg2 - 1
                            openrings[seg1/2] = ring2
                            lineconnect[seg1] = lineconnect[seg2]
                    else:
                        if seg2 & 1 == 0:
                            # new piece links end of 1st ring with start of 2nd
                            ring.append(lineid)
                            ring.extend(ring2)
                            lineconnect[seg1] = lineconnect[seg2+1]
                        else:
                            # new piece links end of both rings
                            ring2.reverse()
                            ring.append(lineid)
                            ring.extend(ring2)
                            seg2 = seg2 - 1
                            lineconnect[seg1] = lineconnect[seg2]
                    del openrings[seg2/2]
                    del lineconnect[seg2]
                    del lineconnect[seg2]
            except ValueError:
                # the pointid2 end is left to be connected
                if seg1 & 1 == 0:
                    ring.insert(0, lineid)
                else:
                    ring.append(lineid)
                lineconnect[seg1] = pointid2
        except ValueError:
            try:
                seg2 = lineconnect.index(pointid2)
                # link on pointid2, pointid1 is left to be connected
                ring = openrings[seg2/2]
                if seg2 & 1 == 0:
                    ring.insert(0, lineid)
                else:
                    ring.append(lineid)
                lineconnect[seg2] = pointid1
            except ValueError:
                # new piece, both ends left to be connected
                openrings.append([ lineid ])
                lineconnect.append(pointid1)
                lineconnect.append(pointid2)
    return len(openrings)


def ringcontains(ring1, ring2):
    """
    Check if coordinates in ring2 are contained in ring1.
    """

    for lon, lat in ring2:
        flg = False
        for i in xrange(1, len(ring1)):
            x1, y1 = ring1[i-1]
            x2, y2 = ring1[i]
            if (lat > y1 and lat <= y2) or (lat > y2 and lat <= y1):
                if lon > x1 + (lat-y1) * (x2-x1) / (y2-y1):
                    flg = not flg
        if not flg:
            return False   # At least 1 point out
    return True


def verify_admin(shapeu, admins):
    """
    Check that all administrative area are closed.

    For the upper level (aggregation of administrative area) also search for
    ring contained in another.
    """

    for dicofre in admins:
        closedrings = []
        if len(dicofre) > 4:
            # Check administrative area read from the shapefile
            # this cannot fail unless something was really wrong
            if findclosedrings(admins[dicofre]["outer"], shapeu, closedrings):
                message("ERROR Area '%s' (DICOFRE=%s) outer ring not closed\n"
                        % (admins[dicofre]["name"], dicofre) )
            if findclosedrings(admins[dicofre]["inner"], shapeu, closedrings):
                message("ERROR Area '%s' (DICOFRE=%s) inner ring not closed\n"
                        % (admins[dicofre]["name"], dicofre) )
        else:
            # Analyze the aggregate administrative area
            if findclosedrings(admins[dicofre]["outer"], shapeu, closedrings):
                message("ERROR Area '%s' (DICOFRE=%s) not closed\n"
                        % (admins[dicofre]["name"], dicofre) )

            # Get coordinates of each ring, compare and detect inner rings
            bboxrings = []
            coordrings = []
            for ring in closedrings:
                coords = []
                for lineid in ring:
                    coordinline = shapeu.getLineCoords(lineid)
                    if coords:
                        # Ensure coordinates are ordered in the ring
                        if coords[-1] == coordinline[-1]:
                            coordinline.reverse()
                        elif coords[0] == coordinline[0]:
                            coords.reverse()
                        elif coords[0] == coordinline[-1]:
                            coords.reverse()
                            coordinline.reverse()
                        coordinline.pop(0)
                    coords.extend(coordinline)
                coordrings.append(coords)

                # Ring bounding box
                xmin, ymin = xmax, ymax = coords[0]
                for lon, lat in coords:
                    xmin = min(xmin, lon)
                    xmax = max(xmax, lon)
                    ymin = min(ymin, lat)
                    ymax = max(ymax, lat)
                bboxrings.append( (xmin, xmax, ymin, ymax) )


            # Compare each ring
            for i in xrange(len(coordrings)):
                for j in xrange(len(coordrings)):
                    if i == j:
                        continue

                    # Check bounding box ring 1 contains bounding box ring 2
                    xmin1, xmax1, ymin1, ymax1 = bboxrings[i]
                    xmin2, xmax2, ymin2, ymax2 = bboxrings[j]
                    if (xmin2 <= xmin1 or xmax2 >= xmax1
                      or ymin2 <= ymin1 or ymax2 >= ymax1):
                        continue

                    # Moving lineids from outer to inner
                    if ringcontains(coordrings[i], coordrings[j]):
                        admins[dicofre]["outer"].difference_update(closedrings[j])
                        admins[dicofre]["inner"].update(closedrings[j])
                        break


def create_caop_table(db):
    """ Recreate caop tables."""

    cursor = db.cursor()

    # Create node tables
    cursor.execute("""DROP TABLE IF EXISTS caop_nodes""")
    cursor.execute("""CREATE TABLE caop_nodes (
                        caop_id bigint NOT NULL,
                        osmid bigint,
                        version int,
                        action character(1)
                      )""")
    cursor.execute("""SELECT AddGeometryColumn('caop_nodes', 'geom',
                                               4326, 'POINT', 2)
                   """)
    cursor.execute("""DROP TABLE IF EXISTS caop_node_tags""")
    cursor.execute("""CREATE TABLE caop_node_tags (
                        caop_id bigint NOT NULL,
                        k text NOT NULL,
                        v text NOT NULL
                      )""")

    # Create way tables
    cursor.execute("""DROP TABLE IF EXISTS caop_ways""")
    cursor.execute("""CREATE TABLE caop_ways (
                        caop_id bigint NOT NULL,
                        osmid bigint,
                        version int,
                        action character(1)
                      )""")
    cursor.execute("""DROP TABLE IF EXISTS caop_way_nodes""")
    cursor.execute("""CREATE TABLE caop_way_nodes (
                        caop_id bigint NOT NULL,
                        node_id bigint NOT NULL,
                        sequence_id int NOT NULL
                      )""")
    cursor.execute("""DROP TABLE IF EXISTS caop_way_tags""")
    cursor.execute("""CREATE TABLE caop_way_tags (
                        caop_id bigint NOT NULL,
                        k text NOT NULL,
                        v text NOT NULL
                      )""")

    # Create relation tables
    cursor.execute("""DROP TABLE IF EXISTS caop_relations""")
    cursor.execute("""CREATE TABLE caop_relations (
                        caop_id bigint NOT NULL,
                        osmid int,
                        version int,
                        action character(1)
                      )""")
    cursor.execute("""DROP TABLE IF EXISTS caop_relation_members""")
    cursor.execute("""CREATE TABLE caop_relation_members (
                        caop_id bigint NOT NULL,
                        member_id bigint NOT NULL,
                        member_type character(1) NOT NULL,
                        member_role text NOT NULL,
                        sequence_id int NOT NULL
                      )""")
    cursor.execute("""DROP TABLE IF EXISTS caop_relation_tags""")
    cursor.execute("""CREATE TABLE caop_relation_tags (
                        caop_id bigint NOT NULL,
                        k text NOT NULL,
                        v text NOT NULL
                      )""")

    # Primary key for node, way, relation
    cursor.execute("""ALTER TABLE caop_nodes
                      ADD CONSTRAINT pk_caop_nodes
                        PRIMARY KEY (caop_id)
                       """)
    cursor.execute("""ALTER TABLE caop_ways
                      ADD CONSTRAINT pk_caop_ways
                        PRIMARY KEY (caop_id)
                   """)
    cursor.execute("""ALTER TABLE caop_relations
                      ADD CONSTRAINT pk_caop_relations
                        PRIMARY KEY (caop_id)
                   """)

    # Primary key for nodes in way, members in relation
    cursor.execute("""ALTER TABLE caop_way_nodes
                      ADD CONSTRAINT pk_caop_way_nodes
                        PRIMARY KEY (caop_id, sequence_id)
                   """)
    cursor.execute("""ALTER TABLE caop_relation_members
                      ADD CONSTRAINT pk_caop_relation_members
                        PRIMARY KEY (caop_id, sequence_id)
                   """)

    # Create index on nodes
    cursor.execute("""CREATE INDEX idx_caop_node_geom
                      ON caop_nodes USING gist (geom)
                   """)

    # Create index for tags
    cursor.execute("""CREATE INDEX idx_caop_node_tags
                      ON caop_node_tags USING btree (caop_id)
                   """)
    cursor.execute("""CREATE INDEX idx_caop_way_tags
                      ON caop_way_tags USING btree (caop_id)
                   """)
    cursor.execute("""CREATE INDEX idx_caop_relation_tags
                      ON caop_relation_tags USING btree (caop_id)
                   """)

    # Auto-incrementing sequence for caop_id
    cursor.execute("""DROP SEQUENCE IF EXISTS seq_caop_id""")
    cursor.execute("""CREATE SEQUENCE seq_caop_id INCREMENT BY -1""")

    db.commit()


def create_temp_table(db):
    """ Create temporary table to assign caop_id to line, point, admin."""

    cursor = db.cursor()

    # Table converting id into unique id
    cursor.execute("""CREATE TEMPORARY TABLE caop_points (
                        point_id int NOT NULL,
                        caop_id bigint NOT NULL
                          DEFAULT nextval('seq_caop_id'),
                        PRIMARY KEY (point_id)
                          )""")
    cursor.execute("""CREATE TEMPORARY TABLE caop_lines (
                        line_id int NOT NULL,
                        caop_id bigint NOT NULL
                          DEFAULT nextval('seq_caop_id'),
                        PRIMARY KEY (line_id)
                          )""")
    cursor.execute("""CREATE TEMPORARY TABLE caop_admins (
                        admin_id int NOT NULL,
                        caop_id bigint NOT NULL
                          DEFAULT nextval('seq_caop_id'),
                            PRIMARY KEY (admin_id)
                      )""")

    db.commit()


def import_caop(db, shapeu, admins):
    """ Import with an unique id all nodes, ways, relations."""

    cursor = db.cursor()

    # Points -> Nodes
    for pointid, coord in shapeu.iterPoints():
        pointwkt = "POINT(%.7f %.7f)" % (coord[0], coord[1])
        cursor.execute("""INSERT INTO caop_points (point_id) VALUES (%s)""",
                       (pointid,) )
        cursor.execute("""INSERT INTO caop_nodes (caop_id, geom) VALUES (
                            currval('seq_caop_id'),
                            ST_GeomFromText(%s, 4326))""", (pointwkt,) )
    db.commit()

    # Lines -> Ways
    for lineid, pntids in shapeu.iterLines():
        cursor.execute("""INSERT INTO caop_lines (line_id) VALUES (%s)""",
                       (lineid,) )
        cursor.execute("""INSERT INTO caop_ways (caop_id) VALUES (
                            currval('seq_caop_id')
                          )""")
        orderpntids = zip(range(len(pntids)), pntids)
        cursor.executemany("""INSERT INTO caop_way_nodes SELECT
                                currval('seq_caop_id'), caop_id, %s
                              FROM caop_points WHERE point_id = %s
                           """, orderpntids)
        cursor.execute("""INSERT INTO caop_way_tags VALUES (
                            currval('seq_caop_id'),
                            'boundary', 'administrative'
                          )""")
        cursor.execute("""INSERT INTO caop_way_tags VALUES (
                            currval('seq_caop_id'),
                            'admin_level', 8
                          )""")
    db.commit()

    # Admins -> Relations
    cpt = 0
    for dicofre in admins:
        cpt += 1
        cursor.execute("""INSERT INTO caop_admins (admin_id) VALUES (%s)""",
                       (cpt,) )
        cursor.execute("""INSERT INTO caop_relations (caop_id) VALUES (
                            currval('seq_caop_id')
                          )""")
        sequenceid = 0
        for role in ("outer", "inner"):
            for lineid in admins[dicofre][role]:
                cursor.execute("""INSERT INTO caop_relation_members SELECT
                                    currval('seq_caop_id'),
                                    caop_id, 'W', %s, %s
                                  FROM caop_lines WHERE line_id = %s
                               """, (role, sequenceid, lineid) )
                sequenceid += 1
        cursor.execute("""INSERT INTO caop_relation_tags VALUES (
                            currval('seq_caop_id'),
                            'type', 'boundary'
                          )""")
        cursor.execute("""INSERT INTO caop_relation_tags VALUES (
                            currval('seq_caop_id'),
                            'boundary', 'administrative'
                          )""")
        cursor.execute("""INSERT INTO caop_relation_tags VALUES (
                            currval('seq_caop_id'),
                            'admin_level', %(level)s
                          )""", admins[dicofre])
        cursor.execute("""INSERT INTO caop_relation_tags VALUES (
                            currval('seq_caop_id'),
                            'name', %(name)s
                          )""", admins[dicofre])
        if admins[dicofre]["level"] < 8:
            cursor.execute("""UPDATE caop_way_tags SET v = %s
                              FROM caop_relation_members AS R
                              WHERE R.caop_id = currval('seq_caop_id')
                              AND caop_way_tags.caop_id = R.member_id
                              AND k = 'admin_level'
                              AND v::int > %s
                           """, (admins[dicofre]["level"],
                                 admins[dicofre]["level"]) )
    db.commit()


def vacuum_analyze_db(db):
    # Update statistics
    isolation_level = db.isolation_level
    db.set_isolation_level(0)
    cursor = db.cursor()
    cursor.execute("VACUUM ANALYZE")
    db.set_isolation_level(isolation_level)


def check_db_caop(db):
    """ Check for special caop table."""

    cursor = db.cursor()
    try:
        cursor.execute("""SELECT max(caop_id) FROM caop_nodes
                          UNION
                          SELECT max(caop_id) FROM caop_ways
                          UNION
                          SELECT max(caop_id) FROM caop_relations
                          UNION
                          SELECT last_value FROM seq_caop_id
                       """)
        cursor.fetchall()  # ignore result, just check if table exists
    except psycopg2.ProgrammingError:
        db.rollback()
        return False
    db.commit()
    return True


def message(txt):
    sys.stderr.write(txt)


def main():
    db = psycopg2.connect(caop_config.dbname)
    if not check_db_caop(db):
        message("Creating PostgreSQL tables\n")
        create_caop_table(db)
    create_temp_table(db)

    shapeu = ShapeUtil(caop_config.cachesize)
    for i in xrange(1, len(sys.argv)):
        message("Reading geometries '%s'\n" % sys.argv[i])
        read_CAOP(sys.argv[i], shapeu)

    message("Simplify geometries\n")
    shapeu.buildSimplifiedLines()

    message("Building administrative area\n")
    admins = {}
    for i in xrange(1, len(sys.argv)):
        admin_CAOP(sys.argv[i], shapeu, admins)
    verify_admin(shapeu, admins)

    message("Importing into database\n")
    import_caop(db, shapeu, admins)
    message("Done\n")
    vacuum_analyze_db(db)


if __name__ == '__main__':
    main()
