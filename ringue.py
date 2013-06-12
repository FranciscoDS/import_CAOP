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

"""
Construct a multi-polygon from a bunch of lines.
"""

class FindClosedRings:
    """
    Group lines in closed rings.

    From a list of unordered lineid construct a list of closed rings.
    From each closed rings we can get the list of ordered lineid or the
    list of ordered pointid.
    """

    RING_CONNECT_BEGIN, RING_CONNECT_END, RING_CONNECT_FIRST = range(3)

    def __init__(self, backend, lines):
        """
        Construct rings for a multipolygon from the list of unordered lines.
        The 'backend' must provide the following methods :
        - getLineEnds(lineid) = return first and last point in line
        - getLineCoords(lineid) = return all points in line
        - isRingValid(points) = is ordered list of points a valid ring
        """

        self.backend = backend
        self.findclosedrings(lines)


    def findclosedrings(self, lines):
        """
        Group lines into rings.
        """

        self.lines = list(lines)
        self.linedone = [ False ] * len(lines)
        self.lineends = []                    # End point ID for each line

        # State for building rings : indice of lines + association direction
        self.lineconnect = []

        # Event in lineconnect to go when backtracking
        self.backstack = []

        # Unclosed ring lines (no more backtrack)
        self.linediscard = []

        for lineid in lines:
            # Store start/end node of each line
            points = self.backend.getLineEnds(lineid)
            if not points:
                # Discard line if not exists
                self.lines.remove(lineid)
                self.linedone.pop()
            else:
                self.lineends.extend(points)

        # Create one ring at a time until no more lines left
        self.newring = True
        while True:
            if self.assemble_ring():
                if self.ringend1 == self.ringend2:
                    # Ring is closed, get geometry and check validity
                    points = self.build_geometry_ring()
                    if self.backend.isRingValid(points):
                        # Even if the ring is valid, do not save the geometry
                        # we will backtrack and build another ring association
                        # if the whole multipolygon is invalid
                        self.newring = True
                        continue
            else:
                # No more ring, all rings must form a valid multipolygon
                # TODO: add check all rings without intersect
                self.group_ring()
                break

            # Ring is not close or have some error (intersect) -> backtrack
            # if no more backtrack to try, discard lines from this ring
            if not self.backtrack():
                self.discard_ring()

        return


    def start_new_ring(self):
        """
        Pick a line and start building a new ring.

        Return False if no more lines to start a ring.
        """

        try:
            ind = self.linedone.index(False)
        except ValueError:
            return False

        # Consume line
        self.linedone[ind] = True
        ind = ind * 2
        self.lineconnect.append( (ind, self.RING_CONNECT_FIRST) )

        # Ring opened, keep track of currently unconnected point ID
        self.ringend1 = self.lineends[ind]
        self.ringend2 = self.lineends[ind + 1]
        self.newring = False
        return True


    def assemble_ring(self):
        """
        Construct a closed ring from the set of lines.

        Return True if an opened/closed ring has been built.
        Return False if no more ring.
        """

        if self.newring:
            if not self.start_new_ring():
                return False
            self.lineidx = 0

        ind = self.lineidx                    # for backtrack purpose
        while self.ringend1 != self.ringend2:
            # Find index of a line connecting with ring
            dirjonction = self.RING_CONNECT_END
            try:
                ind = self.lineends.index(self.ringend2, ind)
            except ValueError:
                dirjonction = self.RING_CONNECT_BEGIN
                try:
                    ind = self.lineends.index(self.ringend1, ind)
                except ValueError:
                    # Assembling finished, ring is not closed
                    return True

            if self.linedone[int(ind/2)]:
                # Line already seen, try another one
                ind = (ind | 1) + 1
                continue

            # Line connected to ring, dirjonction and bit0(ind) tell us where
            # - 0/0 : start ring with start line
            # - 0/1 : start ring with end line
            # - 1/0 : end ring with start line
            # - 1/1 : end ring with end line
            self.lineconnect.append( (ind, dirjonction) )
            self.linedone[int(ind/2)] = True
            if dirjonction == self.RING_CONNECT_END:
                self.ringend2 = self.lineends[ind ^ 1]
            else:
                self.ringend1 = self.lineends[ind ^ 1]

            # Stack possible backtrack point
            if self.lineends.count(self.lineends[ind]) > 2:
                self.backstack.append(len(self.lineconnect)-1)

            # To get next piece
            ind = 0
        return True


    def backtrack(self):
        """
        Rollback up to the next backtrack event.

        Return False if nothing more to retry.
        """

        if not self.backstack:
            # No more backtrack
            return False

        goback = self.backstack.pop()
        while len(self.lineconnect) > goback:
            # Restore ring status and unconsume line
            ind, dirjonction = self.lineconnect.pop()
            self.linedone[int(ind/2)] = False
            if dirjonction == self.RING_CONNECT_FIRST:
                self.newring = True
            elif dirjonction == self.RING_CONNECT_END:
                self.ringend2 = self.lineends[ind]
                self.newring = False
            else:
                self.ringend1 = self.lineends[ind]
                self.newring = False

        # Next retry in assemble_ring()
        self.lineidx = (ind | 1) + 1
        return True


    def discard_ring(self):
        """
        Discard lines of a malformed ring.
        """

        while self.lineconnect:
            # Remove from backtrack but keep line as consumed
            ind, dirjonction = self.lineconnect.pop()
            self.linediscard.append(self.lines[int(ind/2)])

            # Remove up to the beginning of current ring
            if dirjonction == self.RING_CONNECT_FIRST:
                break

        self.backstack = filter(lambda x: x < len(self.lineconnect()),
                                self.backstack)
        self.newring = True


    def build_geometry_ring(self, ringnum=-1):
        """
        Return geometry (ordered list of coordinates) for a ring.
        """

        start, end = self._getconnect_ring(ringnum)
        points = []
        for ind, dirjonction in self.lineconnect[start:end]:
            lstpnt = self.backend.getLineCoords(self.lines[int(ind/2)])
            if dirjonction == self.RING_CONNECT_FIRST:
                points = lstpnt
            elif dirjonction == self.RING_CONNECT_BEGIN:
                if not (ind & 1):
                    # Start of Line connects to start of ring
                    lstpnt.reverse()
                # Prepend line to ring
                points[:1] = lstpnt
            else:
                if (ind & 1):
                    # End of line connects to end of ring
                    lstpnt.reverse()
                # Append line to ring
                points[-1:] = lstpnt
        return points


    def getLineDiscarded(self):
        """
        Return list of lines ID not in a ring.
        """

        return self.linediscard


    def getLineRing(self, ringnum=-1):
        """
        Return ordered list of lines ID for a ring.
        """

        start, end = self._getconnect_ring(ringnum)
        lines = [ self.lines[int(ind/2)]
                  for ind, dirjonction in self.lineconnect[start:end] ]
        return lines


    def nbrRing(self):
        """
        Return number of rings.
        """

        return len( [ i for i in self.lineconnect
                      if i[1] == self.RING_CONNECT_FIRST ])


    def _getconnect_ring(self, ringnum):
        ring_pos = [ i for i, j in enumerate(self.lineconnect)
                      if j[1] == self.RING_CONNECT_FIRST ]
        start = ring_pos[ringnum]
        ring_pos[0] = len(self.lineconnect)
        ringnum = (ringnum+1) % len(ring_pos)
        end = ring_pos[ringnum]
        return (start, end)


    def iterPolygons(self):
        """
        Iterate on each polygon.

        Return (outer ring number, list of inner ring number).
        """

        return self.polygonring.iteritems()


    def getExtentRing(self, ringnum):
        """
        Return bounding box for a ring.

        Return (xmin, xmax, ymin, ymax).
        """

        return self.bboxrings[ringnum]


    def group_ring(self):
        """
        Find inner rings for each outer rings.
        """

        self.polygonring = {}
        nbr = self.nbrRing()
        coordrings = []
        self.bboxrings = []

        # List relationship for a ring
        # - if N is contained by A, B : containedby[N] = [ A, B, ... ]
        # - if N is not contained by other ring : containedby[N] = []
        containedby = [ [] for i in xrange(nbr) ]

        for ring in xrange(nbr):
            # Get coordinates of each ring
            coords = self.build_geometry_ring(ring)
            coordrings.append(coords)

            # Ring bounding box
            xmin = min(coords, key=lambda a: a[0])[0]
            ymin = min(coords, key=lambda a: a[1])[1]
            xmax = max(coords, key=lambda a: a[0])[0]
            ymax = max(coords, key=lambda a: a[1])[1]
            self.bboxrings.append( (xmin, xmax, ymin, ymax) )

        # Compare each ring and cache result in ring contained by ring list
        for i in xrange(nbr):
            for j in xrange(nbr):
                if i == j:
                    continue

                # Check bounding box ring 1 contains bounding box ring 2
                xmin1, xmax1, ymin1, ymax1 = self.bboxrings[i]
                xmin2, xmax2, ymin2, ymax2 = self.bboxrings[j]
                if (xmin2 < xmin1 or xmax2 > xmax1
                  or ymin2 < ymin1 or ymax2 > ymax1):
                    continue

                if ringcontains(coordrings[i], coordrings[j]):
                    containedby[j].append(i)

        # Group ring, find top most ring (parent) and its immediate child
        ringstack = range(nbr)
        while ringstack:
            # Search (upward) outer ring (not contained by other ring)
            outer = ringstack[0]
            while containedby[outer]:
                for ring in containedby[outer]:
                    if ring in ringstack:
                        outer = ring
                        break
                else:
                    break

            # Outer ring is polygon on its own
            self.polygonring[outer] = []
            ringstack.remove(outer)

            # Search and group its inner ring
            for inner in ringstack[:]:
                if outer in containedby[inner]:
                    for ring in containedby[inner]:
                        if ring in ringstack:
                            break
                    else:
                        self.polygonring[outer].append(inner)
                        ringstack.remove(inner)


def ringcontains(ring1, ring2):
    """
    Check if coordinates in ring2 are contained in ring1.
    """

    for lon, lat in ring2:
        flg = False
        for i in xrange(1, len(ring1)):
            x1, y1 = ring1[i-1]
            x2, y2 = ring1[i]
            if (lat < y1 and lat < y2) or (lat > y1 and lat > y2):
                continue
            if (lat == y1 and lon == x1) or (lat == y2 and lon == x2):
                # Consider ring touch as 'in'
                flg = True
                break
            if (lat > y1 and lat <= y2) or (lat > y2 and lat <= y1):
                if lon > x1 + (lat-y1) * (x2-x1) / (y2-y1):
                    flg = not flg
        if not flg:
            # At least 1 point out
            return False
    return True
