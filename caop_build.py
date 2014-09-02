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

# Copyright (C) 2012-2013
#    Francisco Dos Santos <f.dos.santos@free.fr>

import sys
import re
import psycopg2
from cStringIO import StringIO
from osgeo import gdal, ogr, osr
from shapeu import ShapeUtil
from ringue import FindClosedRings
import logo
import caop_config

# GDAL 1.9.0 can do the ISO8859-1 to UTF-8 recoding for us
# but will do it ourself to be backward compatible
gdal.SetConfigOption('SHAPE_ENCODING', '')

# Use SQL operator IN with set() like tuple (reuse tuple adaptation)
psycopg2.extensions.register_adapter(set, lambda x:
                                           psycopg2.extensions.adapt(tuple(x)))


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
    Convert and normalize name from ISO8859 string to UTF8 string.

    Earch word in the name are capitalized except for some portuguese
    preposition.
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

        # First letter of name if the D' is glued with name
        if tok.startswith("D'"):
            tok = "d'" + tok[2:].capitalize()
        tokens[i] = tok

        # Special case: eat the space following a d' preposition
        if tok == "d'" and tokens[i+1] == " ":
            tokens[i+1] = ""

    # Return string in UTF8
    name = ''.join(tokens)
    return name.encode("UTF8")


def read_CAOP(filename, shapeu):
    """
    Read the shapefile and build the geometry.

    We expect only 1 layer of type polygon, coordinates are reprojected
    to WGS84.
    """

    shapefile = ogr.Open(filename)
    layer = shapefile.GetLayer(0)
    layerDef = layer.GetLayerDefn()

    # Verify field and geometry type
    for field in ( "DICOFRE", "MUNICIPIO", "FREGUESIA" ):
        if layerDef.GetFieldIndex(field) == -1:
            raise logo.ERROR("Field '%s' not found" % field)
    if (layerDef.GetFieldIndex("DISTRITO") == -1
      and layerDef.GetFieldIndex("ILHA") == -1):
        raise logo.ERROR("Field 'DISTRITO' or 'ILHA' not found")
    if layerDef.GetGeomType() != ogr.wkbPolygon:
        raise logo.ERROR("Not a POLYGON file")

    # Reproject on the fly
    srcSpatialRef = layer.GetSpatialRef()
    dstSpatialRef = osr.SpatialReference()
    dstSpatialRef.SetWellKnownGeogCS('WGS84')
    transform = osr.CoordinateTransformation(srcSpatialRef, dstSpatialRef)

    # Read each polygon and build the connection arrays (point, segment, line)
    logo.starting("Geometry read", layer.GetFeatureCount())
    for featnum in xrange(layer.GetFeatureCount()):
        logo.progress(featnum)
        feature = layer.GetFeature(featnum)
        geometry  = feature.GetGeometryRef()
        newgeometry = geometry.Clone()
        newgeometry.Transform(transform)

        # Outer Ring (1) followed by Inner Rings (n-1)
        # we create all segments for each ring to find the topology ...
        logo.DEBUG("Feature %d with %d rings" % (featnum,
                   newgeometry.GetGeometryCount()))
        for i in xrange(newgeometry.GetGeometryCount()):
            ring = newgeometry.GetGeometryRef(i)
            lon1, lat1 = ring.GetPoint_2D(0)
            for pnt in xrange(1, ring.GetPointCount()):
                lon2, lat2 = ring.GetPoint_2D(pnt)
                shapeu.makeSegment(lon1, lat1, lon2, lat2)
                lon1, lat1 = lon2, lat2
    logo.ending()


def admin_CAOP(filename, shapeu, admins):
    """
    Reread the shapefile and build each administrative entity.

    Geometry described by a set of lines, attributes converted to UTF8.
    """

    shapefile = ogr.Open(filename)
    layer = shapefile.GetLayer(0)
    layerDef = layer.GetLayerDefn()

    # Detect if we are dealing with Portugal or the autonomous regions
    if layerDef.GetFieldIndex("DISTRITO") != -1:
        logo.DEBUG("Found DISTRITO using admin level 6, 7, 8")
        isregion = False
        toplevel = "DISTRITO"
    elif layerDef.GetFieldIndex("ILHA") != -1:
        logo.DEBUG("Found ILHA using admin level 4, 7, 8")
        isregion = True
        toplevel = "ILHA"

    # Reproject on the fly
    srcSpatialRef = layer.GetSpatialRef()
    dstSpatialRef = osr.SpatialReference()
    dstSpatialRef.SetWellKnownGeogCS('WGS84')
    transform = osr.CoordinateTransformation(srcSpatialRef, dstSpatialRef)

    # Reread each polygon and create the right administrative area
    logo.starting("Attributes read", layer.GetFeatureCount())
    for featnum in xrange(layer.GetFeatureCount()):
        logo.progress(featnum)
        feature = layer.GetFeature(featnum)
        geometry  = feature.GetGeometryRef()
        newgeometry = geometry.Clone()
        newgeometry.Transform(transform)
        dicofre   = feature.GetField("DICOFRE")
        distrito  = convertname(feature.GetField(toplevel))
        municipio = convertname(feature.GetField("MUNICIPIO"))
        freguesia = convertname(feature.GetField("FREGUESIA"))
        logo.DEBUG("Feature %d %s='%s' MUNICIPIO='%s' FREGUESIA='%s'" % (
                   featnum, toplevel, distrito,
                   municipio, freguesia))

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
                                     "outer" : set(),
                                     "bbox" : None
                                   }
        else:
            dicofre1  = dicofre[0:2]
            if not admins.has_key(dicofre1):
                admins[dicofre1] = { "name" : distrito,
                                     "level" : 6,
                                     "inner" : set(),
                                     "outer" : set(),
                                     "bbox" : None
                                   }

        # Municipio
        dicofre2  = dicofre[0:4]
        if not admins.has_key(dicofre2):
            admins[dicofre2] = { "name" : municipio,
                                 "level" : 7,
                                 "inner" : set(),
                                 "outer" : set(),
                                 "bbox" : None
                               }

        # Freguesia
        if not admins.has_key(dicofre):
            admins[dicofre]  = { "name" : freguesia,
                                 "level" : 8,
                                 "inner" : set(),
                                 "outer" : set(),
                                 "bbox" : None
                               }

        # Build sets of lineid, don't distinguish outer and inner rings
        # we deal it later when verifying and grouping rings
        lineset = set()
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
                lineset.add(shapeu.getLine(segment))

        # Update each administrative level
        admins[dicofre]["outer"].update(lineset)
        admins[dicofre2]["outer"].symmetric_difference_update(lineset)
        admins[dicofre1]["outer"].symmetric_difference_update(lineset)
    logo.ending()


def verify_admin(shapeu, admins):
    """
    Check that all administrative area are closed.

    Also search for inner ring and update 'admins'.
    """

    logo.starting("Verify admin area", len(admins))
    verifyinner = {}
    for dicofre in admins:
        logo.progress()
        logo.DEBUG("Area level=%(level)d '%(name)s'" % admins[dicofre])

        # Administrative areas read from the shapefile are also checked
        # and dispatched into outer/inner ring, even if technically only
        # the upper and reconstructed admin level need it (the shapefile
        # already knows what's outer and inner, but we avoid a special
        # case and it cannot fail unless something was really wrong).
        closedrings = FindClosedRings(shapeu, admins[dicofre]["outer"])
        if not closedrings.isValid():
            logo.ERROR("Area '%s' (DICOFRE=%s) not a valid closed ring\n"
                       % (admins[dicofre]["name"], dicofre) )
            for ring, pntid1, pntid2 in closedrings.iterRingDiscarded():
                lineids = closedrings.getLineDiscarded(ring)
                if pntid1 == pntid2:
                    logo.WARN("Ring with %d lines is self-intersecting, still building admin area with this defect"
                              % len(lineids))
                else:
                    points = closedrings.getGeometryDiscarded(ring)
                    logo.WARN("Ring with %d lines is open at %s -> %s, still building admin area with this defect"
                               % (len(lineids), points[0], points[-1]))
            xmin, xmax, ymin, ymax = closedrings.getExtentLineDiscarded()
            admins[dicofre]["bbox"] = [ xmin, xmax, ymin, ymax ]

        # Moving lineids from outer to inner and compute envelope
        for outer, inner in closedrings.iterPolygons():
            for ring in inner:
                lineids = closedrings.getLineRing(ring)
                admins[dicofre]["outer"].difference_update(lineids)
                admins[dicofre]["inner"].update(lineids)
                for line in lineids:
                    # Remember lines used in inner ring for later verification
                    key = (line, admins[dicofre]["level"])
                    verifyinner[key] = [dicofre]

            # Bounding box on outer rings
            xmin, xmax, ymin, ymax = closedrings.getExtentRing(outer)
            if not admins[dicofre]["bbox"]:
                admins[dicofre]["bbox"] = [ xmin, xmax, ymin, ymax ]
            else:
                if xmin < admins[dicofre]["bbox"][0]:
                    admins[dicofre]["bbox"][0] = xmin
                if xmax > admins[dicofre]["bbox"][1]:
                    admins[dicofre]["bbox"][1] = xmax
                if ymin < admins[dicofre]["bbox"][2]:
                    admins[dicofre]["bbox"][2] = ymin
                if ymax > admins[dicofre]["bbox"][3]:
                    admins[dicofre]["bbox"][3] = ymax

    logo.ending()

    # Each inner line on each admin level should be used as outer line
    # in one and only one admin area with the same level
    for dicofre in admins:
        for line in admins[dicofre]["outer"]:
            key = (line, admins[dicofre]["level"])
            if key in verifyinner:
                verifyinner[key].append(dicofre)
    for key in verifyinner:
        if len(verifyinner[key]) != 2:
            dicofre = verifyinner[key][0]
            if len(verifyinner[key]) == 1:
                logo.ERROR("Inner line in area '%s' (DICOFRE=%s) not present as outer in any admin area with level=%d\n"
                           % (admins[dicofre]["name"], dicofre,
                              admins[dicofre]["level"])
                          )
            else:
                logo.ERROR("Inner line in area '%s' (DICOFRE=%s) exist as multiple outer in level=%d : %s\n"
                           % (admins[dicofre]["name"], dicofre,
                              admins[dicofre]["level"],
                              ', '.join([ "%s (DICOFRE=%s)" % (
                                             admins[i]["name"], i)
                                          for i in verifyinner[key][1:] ]))
                          )


def create_caop_table(db):
    """ Recreate caop tables. """

    cursor = db.cursor()

    # Create node tables
    logo.DEBUG("Create Node tables")
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
    logo.DEBUG("Create Way tables")
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
    logo.DEBUG("Create Relation tables")
    cursor.execute("""DROP TABLE IF EXISTS caop_relations""")
    cursor.execute("""CREATE TABLE caop_relations (
                        caop_id bigint NOT NULL,
                        osmid bigint,
                        version int,
                        action character(1)
                      )""")
    cursor.execute("""SELECT AddGeometryColumn('caop_relations', 'bbox',
                                               4326, 'GEOMETRY', 2)
                   """)
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
    logo.DEBUG("Create primary key")
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

    # Create spatial index
    logo.DEBUG("Create index")
    cursor.execute("""CREATE INDEX idx_caop_node_geom
                      ON caop_nodes USING gist (geom)
                   """)
    cursor.execute("""CREATE INDEX idx_caop_relation_bbox
                      ON caop_relations USING gist (bbox)
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
    logo.DEBUG("Create sequence")
    cursor.execute("""DROP SEQUENCE IF EXISTS seq_caop_id""")
    cursor.execute("""CREATE SEQUENCE seq_caop_id INCREMENT BY -1""")

    db.commit()


def create_temp_table(db):
    """
    Create temporary table to assign caop_id to line, point, admin.
    """

    cursor = db.cursor()

    # Table converting id into unique id
    logo.DEBUG("Create Temporary tables")
    cursor.execute("""CREATE TEMPORARY TABLE caop_points (
                        point_id int NOT NULL,
                        caop_id bigint NOT NULL
                          DEFAULT nextval('seq_caop_id'),
                        PRIMARY KEY (point_id)
                          )""")
    cursor.execute("""SELECT AddGeometryColumn('caop_points', 'geom',
                                               4326, 'POINT', 2)
                   """)
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
                        name text NOT NULL,
                        level int NOT NULL,
                        PRIMARY KEY (admin_id)
                      )""")
    cursor.execute("""SELECT AddGeometryColumn('caop_admins', 'bbox',
                                               4326, 'GEOMETRY', 2)
                   """)

    # Table for bulk copy content in lines/admins
    cursor.execute("""CREATE TEMPORARY TABLE caop_linepts (
                        line_id int NOT NULL,
                        sequence_id int NOT NULL,
                        point_id int NOT NULL,
                        PRIMARY KEY (line_id, sequence_id)
                      )""")
    cursor.execute("""CREATE TEMPORARY TABLE caop_adminlines (
                        admin_id int NOT NULL,
                        line_id int NOT NULL,
                        role text NOT NULL,
                        sequence_id int NOT NULL,
                        PRIMARY KEY (admin_id, sequence_id)
                      )""")

    db.commit()


def import_caop(db, shapeu, admins):
    """
    Import with an unique id all nodes, ways, relations.
    """

    cursor = db.cursor()
    logo.starting("Saving nodes, ways, relations",
                  shapeu.nbrPoints() + shapeu.nbrLines() + len(admins))

    # Points -> Nodes
    # - bulk copy to a temp table to get a new unique id
    # - do only one big insert with new ids to the finale table
    logo.DEBUG("Write nodes to database")
    buffcopy = StringIO()
    for pointid, coord in shapeu.iterPoints():
        logo.progress()
        pointEwkt = "SRID=4326;POINT(%.7f %.7f)" % (coord[0], coord[1])
        buffcopy.write("%d\t%s\n" % (pointid, pointEwkt))
    buffcopy.seek(0)
    cursor.copy_from(buffcopy, 'caop_points', columns=('point_id', 'geom'))
    cursor.execute("""INSERT INTO caop_nodes (caop_id, geom)
                      SELECT caop_id, geom FROM caop_points
                   """)
    db.commit()
    buffcopy.close()

    # Lines -> Ways
    # - bulk copy to a temp table to get a new unique id
    # - bulk copy points in lines in a temp table
    # - insert all ways with new ids as administrative level 8
    logo.DEBUG("Write ways to database")
    buffcopy1 = StringIO()
    buffcopy2 = StringIO()
    for lineid, pntids in shapeu.iterLines():
        logo.progress()
        buffcopy1.write("%d\n" % lineid)
        for orderpntid in enumerate(pntids):
            buffcopy2.write("%d\t" % lineid)
            buffcopy2.write("%d\t%d\n" % orderpntid)
    buffcopy1.seek(0)
    cursor.copy_from(buffcopy1, 'caop_lines', columns=('line_id',))
    cursor.execute("""INSERT INTO caop_ways (caop_id)
                      SELECT caop_id FROM caop_lines
                   """)
    buffcopy2.seek(0)
    cursor.copy_from(buffcopy2, 'caop_linepts')
    cursor.execute("""INSERT INTO caop_way_nodes
                      SELECT A.caop_id, B.caop_id, C.sequence_id
                      FROM caop_lines A, caop_points B, caop_linepts C
                      WHERE A.line_id = C.line_id
                      AND C.point_id = B.point_id
                   """)
    cursor.execute("""INSERT INTO caop_way_tags
                      SELECT caop_id, 'boundary', 'administrative'
                      FROM caop_lines
                   """)
    cursor.execute("""INSERT INTO caop_way_tags
                      SELECT caop_id, 'admin_level', 8
                      FROM caop_lines
                   """)
    db.commit()
    buffcopy1.close()
    buffcopy2.close()

    # Admins -> Relations
    # - bulk copy to a temp table to get a new unique id
    # - bulk copy lines in admins in a temp table
    # - correct outer ways administrative level
    # - insert all tags for administrative area
    logo.DEBUG("Write relations to database")
    buffcopy1 = StringIO()
    buffcopy2 = StringIO()
    for (num,dicofre) in enumerate(admins):
        logo.progress()
        buffcopy1.write("%d\t" % num)
        buffcopy1.write("%(name)s\t%(level)d\t" % admins[dicofre])
        buffcopy1.write("SRID=4326;POLYGON((%(x1).7f %(y1).7f,%(x1).7f %(y2).7f,%(x2).7f %(y2).7f,%(x2).7f %(y1).7f,%(x1).7f %(y1).7f))\n" % dict(zip(['x1', 'x2', 'y1', 'y2'], admins[dicofre]['bbox'])) )
        sequenceid = 0
        for role in ("outer", "inner"):
            for lineid in admins[dicofre][role]:
                buffcopy2.write("%d\t%d\t%s\t%d\n" % (
                                num, lineid, role, sequenceid))
                sequenceid += 1
        if admins[dicofre]['level'] < 8:
            cursor.execute("""UPDATE caop_way_tags SET v = %(level)s
                              FROM caop_lines A
                              WHERE caop_way_tags.caop_id = A.caop_id
                              AND A.line_id IN %(outer)s
                              AND k = 'admin_level'
                              AND v::int > %(level)s
                           """, admins[dicofre])
    db.commit()
    buffcopy1.seek(0)
    cursor.copy_from(buffcopy1, 'caop_admins', columns=('admin_id', 'name',
                                                        'level', 'bbox'))
    cursor.execute("""INSERT INTO caop_relations (caop_id, bbox)
                      SELECT caop_id, bbox FROM caop_admins
                   """)
    buffcopy2.seek(0)
    cursor.copy_from(buffcopy2, 'caop_adminlines')
    cursor.execute("""INSERT INTO caop_relation_members
                      SELECT A.caop_id, B.caop_id, 'W', C.role, C.sequence_id
                      FROM caop_admins A, caop_lines B, caop_adminlines C
                      WHERE A.admin_id = C.admin_id
                      AND C.line_id = B.line_id
                   """)
    cursor.execute("""INSERT INTO caop_relation_tags
                      SELECT caop_id, 'type', 'boundary'
                      FROM caop_admins
                   """)
    cursor.execute("""INSERT INTO caop_relation_tags
                      SELECT caop_id, 'boundary', 'administrative'
                      FROM caop_admins
                   """)
    cursor.execute("""INSERT INTO caop_relation_tags
                      SELECT caop_id, 'admin_level', level::text
                      FROM caop_admins
                   """)
    cursor.execute("""INSERT INTO caop_relation_tags
                      SELECT caop_id, 'name', name
                      FROM caop_admins
                   """)
    db.commit()
    buffcopy1.close()
    buffcopy2.close()
    logo.ending()


def vacuum_analyze_db(db):
    """ Update DB statistics. """

    logo.DEBUG("Vacuum Analyze")
    isolation_level = db.isolation_level
    db.set_isolation_level(0)
    cursor = db.cursor()
    cursor.execute("VACUUM ANALYZE")
    db.set_isolation_level(isolation_level)


def check_db_caop(db):
    """ Check for special caop tables. """

    logo.DEBUG("Checking for CAOP tables ...")
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
        logo.DEBUG("... no CAOP tables")
        return False
    db.commit()
    logo.DEBUG("... CAOP tables exists")
    return True


def main():
    logo.init(filename = caop_config.logfile,
              verbose = caop_config.verbose,
              progress = caop_config.progress)
    if len(sys.argv) < 2:
        raise logo.ERROR("Missing input Shapefile")

    logo.DEBUG("Connect to DB(%s)" % caop_config.dbname)
    db = psycopg2.connect(caop_config.dbname)
    if not check_db_caop(db):
        logo.INFO("Creating PostgreSQL tables")
        create_caop_table(db)
    create_temp_table(db)

    shapeu = ShapeUtil(caop_config.cachesize)
    for i in xrange(1, len(sys.argv)):
        logo.INFO("Reading geometries '%s'" % sys.argv[i])
        read_CAOP(sys.argv[i], shapeu)

    logo.INFO("Simplify geometries")
    shapeu.buildSimplifiedLines()

    logo.INFO("Building administrative area")
    admins = {}
    for i in xrange(1, len(sys.argv)):
        admin_CAOP(sys.argv[i], shapeu, admins)
    logo.INFO("Verifying administrative area")
    verify_admin(shapeu, admins)

    logo.INFO("Importing into database")
    import_caop(db, shapeu, admins)
    vacuum_analyze_db(db)
    logo.close()


if __name__ == '__main__':
    main()
