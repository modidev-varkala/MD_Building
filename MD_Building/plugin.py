import math
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon, QColor, QKeySequence
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import (
    Qgis, QgsWkbTypes, QgsPointXY, QgsGeometry, QgsFeature,
    QgsCoordinateTransform, QgsProject, QgsVectorLayer
)
from qgis.gui import QgsMapTool, QgsRubberBand


class BuildingCaptureTool(QgsMapTool):
    def __init__(self, iface, finished_callback):
        super().__init__(iface.mapCanvas())
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.finished_callback = finished_callback
        self.points = []
        self.cursor_point = None
        self.rubber = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.rubber.setColor(QColor(230, 35, 35, 220))
        self.rubber.setFillColor(QColor(230, 35, 35, 35))
        self.rubber.setWidth(2)
        self.rubber.setLineStyle(Qt.DashLine)
        self.setCursor(Qt.CrossCursor)

    def _xy(self, event):
        return self.toMapCoordinates(event.pos())

    @staticmethod
    def _project_to_axis(point, origin, axis):
        dx = point.x() - origin.x()
        dy = point.y() - origin.y()
        t = dx * axis[0] + dy * axis[1]
        return QgsPointXY(origin.x() + t * axis[0], origin.y() + t * axis[1])

    def _axes(self):
        if len(self.points) < 2:
            return None, None
        a, b = self.points[0], self.points[1]
        dx, dy = b.x() - a.x(), b.y() - a.y()
        length = math.hypot(dx, dy)
        if length < 1e-9:
            return None, None
        u = (dx / length, dy / length)
        v = (-u[1], u[0])
        return u, v

    def _constrained_point(self, raw):
        if len(self.points) < 2:
            return raw
        u, v = self._axes()
        if u is None:
            return raw
        # After the baseline, alternate perpendicular and parallel edges.
        axis = v if (len(self.points) - 1) % 2 == 1 else u
        return self._project_to_axis(raw, self.points[-1], axis)

    def _update_rubber(self, preview=None):
        self.rubber.reset(QgsWkbTypes.LineGeometry)
        pts = list(self.points)
        if preview is not None:
            if not pts or math.hypot(preview.x()-pts[-1].x(), preview.y()-pts[-1].y()) > 1e-8:
                pts.append(preview)
        if len(pts) >= 2:
            # Rubber-band polygon preview is intentionally open while digitizing.
            self.rubber.addGeometry(QgsGeometry.fromPolylineXY(pts), None)

    def canvasMoveEvent(self, event):
        raw = self._xy(event)
        if self.points:
            preview = self._constrained_point(raw)
        else:
            preview = raw
        self.cursor_point = preview
        self._update_rubber(preview)

    def canvasPressEvent(self, event):
        if event.button() == Qt.RightButton:
            if len(self.points) >= 3:
                # The last LEFT-click is the user's approximate blue endpoint.
                # Do not use the right-click location, which is only the finish command.
                self._finish(self.points[-1])
            else:
                self._cancel()
            return
        if event.button() != Qt.LeftButton:
            return
        raw = self._xy(event)
        p = raw if len(self.points) < 2 else self._constrained_point(raw)
        if self.points and math.hypot(p.x()-self.points[-1].x(), p.y()-self.points[-1].y()) < 1e-8:
            return
        self.points.append(p)
        self._update_rubber()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            event.accept()
            self._cancel()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            event.accept()
            if len(self.points) >= 3:
                self._finish(self.points[-1])
            else:
                self._message('Add at least three corners before finishing the building.')
        elif key in (Qt.Key_Backspace, Qt.Key_Delete) or (
                key == Qt.Key_Z and event.modifiers() & Qt.ControlModifier):
            event.accept()
            if self.points:
                self.points.pop()
                self._update_rubber(self.cursor_point if self.points else None)
        else:
            event.ignore()

    def _finish(self, raw_end):
        u, v = self._axes()
        if u is None:
            self._message('The first two points must be different.')
            return
        # The final vertex is snapped onto the perpendicular axis through the
        # starting point, making the closing edge exactly 90 degrees to edge 1.
        end = self._project_to_axis(raw_end, self.points[0], v)
        # Replace the approximate final (blue) click with its projection onto
        # the perpendicular guide through the first (green) point. This guide
        # is the orange 90-degree line defined by the first edge.
        ring = list(self.points[:-1]) + [end]
        if len(ring) < 3:
            self._message('Add at least three corners before finishing the building.')
            return
        if math.hypot(ring[-1].x()-ring[0].x(), ring[-1].y()-ring[0].y()) < 1e-8:
            self._message('The closing point is too close to the starting point. Move the pointer and right-click again.')
            return
        closed = ring + [ring[0]]
        geom = QgsGeometry.fromPolygonXY([closed])
        if geom.isEmpty() or geom.area() <= 1e-8 or not geom.isGeosValid():
            self._message('Invalid or self-intersecting outline. Adjust the corners and right-click again.')
            return
        if not self._save_geometry(geom):
            return
        # Stay active: reset and be ready for the next building.
        self._reset()
        self.iface.messageBar().pushSuccess('MD_Building', 'Building saved. Ready for the next one (Esc or right-click with no points to stop).')

    def _save_geometry(self, map_geom):
        layer = self.iface.activeLayer()
        if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
            self._message('Select your existing polygon shapefile layer first.')
            return False
        if QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.PolygonGeometry:
            self._message('The active layer is not a polygon layer. Select your building polygon shapefile.')
            return False
        project_crs = self.canvas.mapSettings().destinationCrs()
        layer_crs = layer.crs()
        geom = QgsGeometry(map_geom)
        if project_crs != layer_crs:
            transform = QgsCoordinateTransform(project_crs, layer_crs, QgsProject.instance())
            result = geom.transform(transform)
            if result != Qgis.GeometryOperationResult.Success:
                self._message('Could not transform the outline to the active layer CRS.')
                return False
        started_here = False
        if not layer.isEditable():
            if not layer.startEditing():
                self._message('Could not start editing the active layer.')
                return False
            started_here = True
        feature = QgsFeature(layer.fields())
        feature.setGeometry(geom)
        if not layer.addFeature(feature):
            if started_here:
                layer.rollBack()
            self._message('Could not add the building to the active layer.')
            return False
        new_fid = feature.id()
        if started_here and not layer.commitChanges():
            layer.rollBack()
            self._message('Could not save changes: ' + '; '.join(layer.commitErrors()))
            return False
        layer.updateExtents()
        if new_fid is not None and new_fid >= 0:
            layer.selectByIds([new_fid])
        self.iface.setActiveLayer(layer)
        self.canvas.refresh()
        return True

    def _message(self, msg):
        self.iface.messageBar().pushWarning('MD_Building', msg)

    def _cleanup(self):
        self.rubber.reset(QgsWkbTypes.LineGeometry)

    def _reset(self):
        self._cleanup()
        self.points = []
        self.cursor_point = None

    def _cancel(self):
        """Discard the building in progress; if nothing is in progress, exit the tool."""
        if self.points:
            self._reset()
        else:
            self._reset()
            self.finished_callback(self)

    def deactivate(self):
        self._cleanup()
        super().deactivate()


DEFAULT_SHORTCUT = 'Ctrl+Alt+B'


class MD_Building:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.tool = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.svg')
        self.action = QAction(QIcon(icon_path), 'MD_Building', self.iface.mainWindow())
        self.action.setToolTip(
            'MD_Building (%s) — left-click corners, right-click or Enter to finish, '
            'Backspace to undo, Esc to cancel' % DEFAULT_SHORTCUT)
        self.action.setObjectName('mdBuildingAction')
        self.action.setShortcut(QKeySequence(DEFAULT_SHORTCUT))
        self.action.setShortcutContext(Qt.ApplicationShortcut)
        self.action.triggered.connect(self.start_capture)
        # Registers the action in Settings > Keyboard Shortcuts so the user can rebind it.
        self.iface.registerMainWindowAction(self.action, DEFAULT_SHORTCUT)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu('&MD_Building', self.action)

    def start_capture(self):
        if self.tool is not None:
            self.tool._cleanup()
        self.tool = BuildingCaptureTool(self.iface, self._tool_finished)
        self.iface.mapCanvas().setMapTool(self.tool)
        self.iface.messageBar().pushInfo('MD_Building', 'Left-click to add corners. Right-click or Enter to finish (tool stays active for the next building); Backspace undoes a corner; Esc cancels (press again to exit).')

    def _tool_finished(self, tool):
        if self.iface.mapCanvas().mapTool() is tool:
            self.iface.mapCanvas().unsetMapTool(tool)
        self.tool = None

    def unload(self):
        if self.tool is not None:
            self.tool._cleanup()
            if self.iface.mapCanvas().mapTool() is self.tool:
                self.iface.mapCanvas().unsetMapTool(self.tool)
            self.tool = None
        if self.action is not None:
            self.iface.unregisterMainWindowAction(self.action)
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu('&MD_Building', self.action)
            self.action = None
