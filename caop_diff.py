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

# Copyright (C) 2013
#    Francisco Dos Santos <f.dos.santos@free.fr>

import psycopg2
from cStringIO import StringIO
import ringue
import logo
import caop_config

#
# Definitions
#

boundingbox = [
    'BOX( -9.554 36.919,  -6.188 42.156)', # Portugal
    'BOX(-17.830 29.684, -15.435 33.610)', # Madeira
    'BOX(-32.507 35.160, -24.069 40.502)', # Azores
]


#
# Functions
#

def create_table(db):
    """
    Create temporary working table.
    """

    cursor = db.cursor()

    # Table linking admin area OSM <--> CAOP
    cursor.execute("""DROP TABLE IF EXISTS matching_relation""")
    cursor.execute("""CREATE TABLE matching_relation (
                        osm_id bigint NOT NULL,
                        version int,
                        admin_level text,
                        name text,
                        associationid bigint
                      )""")
    cursor.execute("""SELECT AddGeometryColumn('matching_relation', 'bbox',
                                               4326, 'GEOMETRY', 2)
                   """)
    cursor.execute("""SELECT AddGeometryColumn('matching_relation', 'geom',
                                               4326, 'GEOMETRY', 2)
                   """)

    cursor.execute("""ALTER TABLE matching_relation
                      ADD CONSTRAINT pk_matching_relation
                        PRIMARY KEY (osm_id)
                   """)
    cursor.execute("""CREATE INDEX idx_matching_relation_bbox
                      ON matching_relation USING GiST (bbox)
                   """)


    # Table building each ring geometry
    cursor.execute("""DROP TABLE IF EXISTS building_ring_polygon""")
    cursor.execute("""CREATE TABLE building_ring_polygon (
                        id bigint NOT NULL,
                        ring int NOT NULL
                      )""")
    cursor.execute("""SELECT AddGeometryColumn('building_ring_polygon', 'geom',
                                               4326, 'POLYGON', 2)
                   """)

    cursor.execute("""ALTER TABLE building_ring_polygon
                      ADD CONSTRAINT pk_building_ring_polygon
                        PRIMARY KEY (id, ring)
                   """)
    cursor.execute("""CREATE INDEX idx_building_ring_polygon_geom
                      ON building_ring_polygon USING GiST (geom)
                   """)

    cursor.close()
    db.commit()


def prepare_table(db):
    """
    Select relation of interest. Choose admin relation entirely
    contained in pre-defined 'boundingbox'.
    """

    cursor = db.cursor()

    sqlparam = {}
    sqlselect = []
    for cpt, box in enumerate(boundingbox):
        sqlparam["box%d" % cpt] = box
        sqlselect.append("""SELECT id, version
                            FROM relations A, relation_tags B
                            WHERE A.id = B.relation_id
                            AND B.k = 'admin_level'
                            AND A.bbox && ST_SetSRID(%%(box%d)s::box2d, 4326)
                         """ % cpt)
        sqlselect.append("""SELECT id, version
                            FROM relations A, relation_tags B
                            WHERE A.id = B.relation_id
                            AND B.k = 'boundary' AND B.v = 'administrative'
                            AND A.bbox && ST_SetSRID(%%(box%d)s::box2d, 4326)
                         """ % cpt)
        sqlselect.append("""SELECT id, version
                            FROM relations A, relation_tags B
                            WHERE A.id = B.relation_id
                            AND B.k = 'source' AND B.v LIKE 'CAOP%%%%'
                            AND A.bbox && ST_SetSRID(%%(box%d)s::box2d, 4326)
                         """ % cpt)

    # Execute one really big sql request
    cursor.execute("""INSERT INTO matching_relation (osm_id, version)
                   """ + " UNION ".join(sqlselect), sqlparam)

    # Copy most important relation attributes
    cursor.execute("""UPDATE matching_relation A
                      SET bbox = (
                        SELECT bbox
                        FROM relations B
                        WHERE A.osm_id = B.id
                      ), admin_level = (
                        SELECT B.v
                        FROM relation_tags B
                        WHERE A.osm_id = B.relation_id
                        AND B.k = 'admin_level'
                      ), name = (
                        SELECT B.v
                        FROM relation_tags B
                        WHERE A.osm_id = B.relation_id
                        AND B.k = 'name'
                      )
                   """)

    cursor.close()
    db.commit()


class MatchRelation:
    """
    Base class comparing CAOP relation with OSM relation.

    Do not use - see MatchRelationBbox and MatchRelationGeom.
    """

    def __init__(self, db):
        self.db = db
        self.adminlvl = None


    def link_caop_osm(self, adminlvl):
        """
        Search the OSM relation fitting the CAOP admin area.

        Link each CAOP relation in 'adminlvl' with the best
        existing OSM relation.
        """

        self.adminlvl = adminlvl
        cursor = self.db.cursor()

        # Search for each caop relation the unlinked osm relation
        # fitting the area
        cursor.execute("""SELECT A.caop_id
                          FROM caop_relations A, caop_relation_tags B
                          WHERE A.caop_id = B.caop_id
                          AND B.k = 'admin_level' AND B.v = %s
                          AND NOT EXISTS (SELECT 1 FROM matching_relation
                             WHERE associationid = A.caop_id)
                       """, (str(adminlvl),) )
        data = cursor.fetchall()
        cursor.close()
        self.db.commit()

        logo.starting("Searching for admin level %d" % adminlvl, len(data))
        for (caop_id,) in data:
            logo.progress()
            self.best_match = None
            self.do_search_admin(caop_id)   #  Delegate
            if self.best_match:
                logo.DEBUG("Found for caop %s osm=%s)" % (caop_id, self.best_match))
                if self.best_match.adminlvl != self.adminlvl:
                    logo.WARN("Relation found with unmatched admin level caop=%s (%s), osm=%s (%s)"
                              % (caop_id, self.adminlvl,
                                 self.best_match.osm_id,
                                 self.best_match.adminlvl))
                self.set_association(caop_id, self.best_match.osm_id)
            else:
                logo.DEBUG("No relation found for caop=%s" % caop_id)
        logo.ending()


    def search_best_match(self, caop_id, data):
        """
        Compare area and choose the best match.
        """

        data = self.Data(data)
        if not self.best_match:
            self.best_match = data
        elif abs(data.disjoint - self.best_match.disjoint) < 1.0e-5:
            # Choose between the less disjoint area and the one with the
            # same admin level
            if data.is_level(self.adminlvl) and not self.best_match.is_level(self.adminlvl):
                self.best_match = data
            elif data.intersect > self.best_match.intersect:
                # Cannot decide if the best match offers less intersect area
                if ( (data.is_level(self.adminlvl) and
                      self.best_match.is_level(self.adminlvl)) or
                     (not data.is_level(self.adminlvl) and
                      not self.best_match.is_level(data.adminlvl)) ):
                   logo.ERROR("Cannot choose for caop=%s between osm=%s and osm=%s"
                              % (caop_id, self.best_match, data))


    def set_association(self, caop_id, osm_id):
        """
        Link an existing OSM relation with CAOP relation.
        """

        cursor = self.db.cursor()
        cursor.execute("""UPDATE matching_relation
                          SET associationid = %s
                          WHERE osm_id = %s
                       """, (caop_id, osm_id) )
        cursor.close()
        self.db.commit()


    class Data:
        def __init__(self, data):
            """
            Encapsulate OSM/CAOP comparison result.
            """

            self.osm_id = data[0]
            try:
                self.adminlvl = int(data[1])
            except (ValueError, TypeError):
                self.adminlvl = None
            self.name = data[2]
            self.disjoint = data[3]
            self.intersect = data[4]


        def __str__(self):
            return "%s (lvl=%s) : '%s' --> score %.8f %.8f" % (
                   self.osm_id, self.adminlvl, self.name,
                   self.disjoint, self.intersect)


        def is_level(self, admin_level):
            return self.adminlvl == admin_level


class MatchRelationBbox(MatchRelation):
    """
    Compare CAOP relation with OSM relation using bounding box.
    """

    def do_search_admin(self, caop_id):
        cursor = self.db.cursor()
        cursor.execute("""SELECT B.osm_id, B.admin_level, B.name,
                            ST_Area(ST_SymDifference(A.bbox, B.bbox)) AS diff,
                            ST_Area(ST_Intersection(A.bbox, B.bbox))
                          FROM caop_relations A, matching_relation B
                          WHERE B.bbox && A.bbox AND A.caop_id = %s
                          AND B.associationid IS NULL
                          AND ST_Area(ST_SymDifference(A.bbox, B.bbox)) < ST_Area(ST_Intersection(A.bbox, B.bbox)) / 2
                          ORDER BY diff
                       """, (caop_id,))
        for data in cursor.fetchall():
            self.search_best_match(caop_id, data)
        cursor.close()


class MatchRelationGeom(MatchRelation):
    """
    Compare CAOP relation with OSM relation using geometry.
    """

    def do_search_admin(self, caop_id):
        cursor = self.db.cursor()

        # Build geometry for CAOP relation
        DBGeometryRingCAOP(self.db).buildgeometry(caop_id)

        # Build geometry for OSM relations involved in comparison (if any
        # and if not already build)
        cursor.execute("""SELECT B.osm_id
                          FROM caop_relations A, matching_relation B
                          WHERE B.bbox && A.bbox AND A.caop_id = %s
                          AND B.associationid IS NULL AND B.geom IS NULL
                       """, (caop_id,))
        build_list = [ data[0] for data in cursor.fetchall() ]
        if build_list:
            for osm_id in build_list:
                DBGeometryRingOSM(self.db).buildgeometry(osm_id)
            # Keep OSM geometry as multipolygons
            cursor.execute("""UPDATE matching_relation A
                              SET geom = B.geom
                              FROM
                               (SELECT id, ST_Collect(geom) AS geom
                                FROM building_ring_polygon
                                WHERE id IN %s
                                GROUP BY id) AS B
                              WHERE A.osm_id = B.id
                           """, (tuple(build_list),) )
            self.db.commit()

        # Intersection/SymDifference are slow for very big geometries
        # we ilter out all the unprobable areas
        cursor.execute("""SELECT B.osm_id, B.admin_level, B.name,
                            ST_Area(ST_SymDifference(C.geom, B.geom)) AS diff,
                            ST_Area(ST_Intersection(C.geom, B.geom))
                          FROM caop_relations A, matching_relation B,
                           (SELECT ST_Collect(geom) AS geom
                            FROM building_ring_polygon
                            WHERE id = %s) AS C
                          WHERE B.bbox && A.bbox AND A.caop_id = %s
                          AND B.associationid IS NULL
                          AND ST_Area(B.geom) < ST_Area(C.geom)*2
                          AND ST_Area(B.geom) > ST_Area(C.geom)/2
                          AND ST_Area(ST_SymDifference(C.geom, B.geom))
                             < ST_Area(ST_Intersection(C.geom, B.geom))
                          ORDER BY diff
                       """, (caop_id, caop_id))
        for data in cursor.fetchall():
            self.search_best_match(caop_id, data)
        cursor.close()


class DBGeometryRing:
    """
    Base class for building outer rings geometry.

    Do not use - see DBGeometryRingOSM and DBGeometryRingCAOP.
    """

    def __init__(self, db):
        self.db = db


    def buildgeometry(self, adminid):
        """
        Build a polygon for each ring from relation 'adminid'.

        Only outer rings are built.
        """

        lines = self.getOuterMembers(adminid)
        rings = ringue.FindClosedRings(self, lines)
        for ringnum in range(rings.nbrRing()):
            points = rings.build_geometry_ring(ringnum)
            self.savebuildring(adminid, ringnum, points)
        self.db.commit()


    def isRingValid(self, outer_points):
        """
        Test if 'outer_points' is a valid polygon.
        """

        cursor = self.db.cursor()
        outer = ', '.join([ "%f %f" % coord for coord in outer_points ])
        polygon = 'POLYGON((%s))' % outer
        cursor.execute("""SELECT ST_IsValid(ST_GeomFromText(%s))""", (polygon,))
        result = cursor.fetchone()[0]
        return result


    def savebuildring(self, adminid, ringnumber, points):
        """
        Save ring geometry as a polygon.
        """

        cursor = self.db.cursor()
        buffcopy = StringIO()
        ringEwkt = "SRID=4326;POLYGON((%s))" % ",".join( [ "%.7f %.7f" %
                     (pt[0], pt[1]) for pt in points ] )
        buffcopy.write("%d\t%d\t%s\n" % (adminid, ringnumber, ringEwkt))
        buffcopy.seek(0)
        cursor.copy_from(buffcopy, 'building_ring_polygon', columns=('id', 'ring', 'geom'))
        cursor.close()
        self.db.commit()
        buffcopy.close()


class DBGeometryRingOSM(DBGeometryRing):
    """
    Building outer rings geometry from OSM relation.
    """

    def getOuterMembers(self, adminid):
        """
        Return list of ways in relation.
        """

        cursor = self.db.cursor()
        cursor.execute("""SELECT member_id
                          FROM relation_members
                          WHERE relation_id = %s AND member_type = 'W'
                          AND member_role IN ('outer', '')
                       """, (adminid,) )
        lines = [ data[0] for data in cursor.fetchall() ]
        cursor.close()
        return lines


    def getLineEnds(self, lineid):
        """
        Return first and last node in way.

        Return None if way doesn't exist.
        """

        cursor = self.db.cursor()
        cursor.execute("""SELECT node_id FROM way_nodes
                          WHERE way_id = %s
                          ORDER BY sequence_id ASC
                          LIMIT 1
                       """, (lineid,) )
        data = cursor.fetchone()
        if data is None:
            return None
        pointid1 = data[0]
        cursor.execute("""SELECT node_id FROM way_nodes
                          WHERE way_id = %s
                          ORDER BY sequence_id DESC
                          LIMIT 1
                       """, (lineid,) )
        pointid2 = cursor.fetchone()[0]
        cursor.close()
        return (pointid1, pointid2)


    def getLineCoords(self, lineid):
        """
        Return list of coordinates for all nodes in way.
        """

        cursor = self.db.cursor()
        cursor.execute("""SELECT ST_X(A.geom), ST_Y(A.geom)
                          FROM nodes A, way_nodes B
                          WHERE A.id = B.node_id
                          AND B.way_id = %s
                          ORDER BY sequence_id
                       """ % (lineid,))
        points = [ pt for pt in cursor.fetchall() ]
        cursor.close()
        return points


class DBGeometryRingCAOP(DBGeometryRing):
    """
    Building outer rings geometry from CAOP relation.
    """

    def getOuterMembers(self, adminid):
        """
        Return list of ways in relation.
        """

        cursor = self.db.cursor()
        cursor.execute("""SELECT member_id
                          FROM caop_relation_members
                          WHERE caop_id = %s AND member_type = 'W'
                          AND member_role = 'outer'
                       """, (adminid,) )
        lines = [ data[0] for data in cursor.fetchall() ]
        cursor.close()
        return lines


    def getLineEnds(self, lineid):
        """
        Return first and last node in way.
        """

        cursor = self.db.cursor()
        cursor.execute("""SELECT node_id FROM caop_way_nodes
                          WHERE caop_id = %s
                          ORDER BY sequence_id ASC
                          LIMIT 1
                       """, (lineid,) )
        pointid1 = cursor.fetchone()[0]
        cursor.execute("""SELECT node_id FROM caop_way_nodes
                          WHERE caop_id = %s
                          ORDER BY sequence_id DESC
                          LIMIT 1
                       """, (lineid,) )
        pointid2 = cursor.fetchone()[0]
        cursor.close()
        return (pointid1, pointid2)


    def getLineCoords(self, lineid):
        """
        Return list of coordinates for all nodes in way.
        """

        cursor = self.db.cursor()
        cursor.execute("""SELECT ST_X(A.geom), ST_Y(A.geom)
                          FROM caop_nodes A, caop_way_nodes B
                          WHERE A.caop_id = B.node_id
                          AND B.caop_id = %s
                          ORDER BY sequence_id
                       """ % (lineid,))
        points = [ pt for pt in cursor.fetchall() ]
        cursor.close()
        return points


def main():
    logo.init(filename = caop_config.logfile,
              verbose = caop_config.verbose,
              progress = caop_config.progress)
    logo.DEBUG("Connect to DB(%s)" % caop_config.dbname)
    db = psycopg2.connect(caop_config.dbname)
    create_table(db)
    prepare_table(db)

    # Search OSM admin area using bounding box
    logo.INFO("Search existing admin area by bounding box")
    matching = MatchRelationBbox(db)
    for adminlevel in (4, 6, 7, 8):
        matching.link_caop_osm(adminlevel)

    # Search OSM admin area using geometry
    matching = MatchRelationGeom(db)
    logo.INFO("Search existing admin area by geometry")
    for adminlevel in (8, 7, 6, 4):
        matching.link_caop_osm(adminlevel)


if __name__ == '__main__':
    main()
