import PySide2.QtCore as QtC
import PySide2.QtGui as QtG

import PIL as PIL
import PIL.ImageQt as PILQt

# TODO: Have this be configured by zooming in and out
iconSize = QtC.QSize(100, 100)

# Custom view/model role - for getting and setting PIL Images
ImageRole = QtC.Qt.UserRole

# Wrapper class around an RSI state, for use in the editor
class State(QtC.QAbstractTableModel):
    def __init__(self, parentRsi, stateName, parent = None):
        QtC.QAbstractTableModel.__init__(self, parent)

        self.state = parentRsi.states[stateName]
        self.animations = [QtC.QSequentialAnimationGroup() for i in range(self.state.directions)]
        self.recalculateSummary()
        self.dataChanged.connect(self.frameDataChanged)
 
        self.rowsInserted.connect(lambda _parent, _first, _last: self.recalculateSummary())
        self.rowsRemoved.connect(lambda _parent, _first, _last: self.recalculateSummary())
        self.rowsMoved.connect(lambda _source, _first, _last, _dest, _destfirst: self.recalculateSummary())
        self.columnsInserted.connect(lambda _parent, _first, _last: self.recalculateSummary())
        self.columnsRemoved.connect(lambda _parent, _first, _last: self.recalculateSummary())
        self.columnsMoved.connect(lambda _source, _first, _last, _dest, _destfirst: self.recalculateSummary())

    # Getters

    def name(self):
        return self.state.name

    def directions(self):
        return self.state.directions

    # Convenience function - get pairs of images and delays for the given direction
    def frames(self, direction):
        return list(zip(self.state.icons[direction], self.getDelays(direction)))

    def getDelays(self, direction):
        if self.state.delays[direction] == []:
            return [None]
        else:
            return self.state.delays[direction]

    def setDelay(self, index, delay):
        direction = index.row()
        frame = index.column() 
        
        leftMostChange = frame

        if len(self.state.delays[direction]) <= frame:
            leftMostChange = len(self.state.delays[direction])
            self.state.delays[direction].extend([0.0] * (frame - len(self.state.delays[direction]) + 1))

        self.state.delays[direction][frame] = delay

        self.dataChanged.emit(self.index(direction, leftMostChange), self.index(direction, frame), [QtC.Qt.DisplayRole])

    def frame(self, index):
        return self.data(index, role=ImageRole)

    def setFrame(self, index, image):
        direction = index.row()
        frame = index.column() 

        leftMostChange = frame

        if len(self.state.icons[direction]) <= frame:
            leftMostChange = len(self.state.icons[direction])
            self.state.icons[direction].extend([None] * (frame - len(self.state.icons[direction]) + 1))

        self.state.icons[direction][frame] = image.copy()

        self.dataChanged.emit(self.index(direction, leftMostChange), self.index(direction, frame), [QtC.Qt.DecorationRole])

    def getDirFrame(self, index):
        framesInDirection = self.frames(index.row())
        if index.column() >= len(framesInDirection):
            return None
        return (index.row(), index.column())

    # Frame manipulations

    def addFrame(self, index, image = None, delay = 0.0):
        if image is None:
            image = PIL.Image.new('RGBA', self.state.size)

        columnEnd = self.columnCount(QtC.QModelIndex()) - 1
        # In this case, we're going to insert a column
        insertColumn =  len(self.state.icons[index.row()]) == columnEnd

        if insertColumn:
            self.beginInsertColumns(QtC.QModelIndex(), columnEnd, columnEnd)

        self.state.icons[index.row()].insert(index.column(), image)
        self.state.delays[index.row()].insert(index.column(), delay)

        if insertColumn:
            self.endInsertColumns()
        
        self.dataChanged.emit(index, index.siblingAtColumn(self.columnCount(QtC.QModelIndex()) - 1))

    def deleteFrame(self, index):
        removeColumn = True
        columnCount = self.columnCount(QtC.QModelIndex()) - 1
        for direction in range(self.directions()):
            if direction == index.row():
                continue

            # Remove the column if all other directions *DON'T* have a frame in it
            removeColumn = removeColumn and (len(self.state.icons[direction]) != columnCount)

        # If this is the case, removing this frame should delete the final column
        if removeColumn:
            self.beginRemoveColumns(QtC.QModelIndex(), columnCount - 1, columnCount - 1)

        image = self.state.icons[index.row()].pop(index.column())
        delay = self.state.delays[index.row()].pop(index.column())
        if removeColumn:
            self.endRemoveColumns()

        newColumnCount = self.columnCount(QtC.QModelIndex())
        if index.column() >= newColumnCount:
            self.dataChanged.emit(index, index.siblingAtColumn(newColumnCount - 1))

        return (image, delay) 

    # Direction manipulations

    ## Returns: ( <removed icon lists>, <removed delay lists> )
    def setDirections(self, directions):
        if self.directions() == directions:
            return ([], [])

        if self.directions() > directions:
            firstRemoved = directions
            lastRemoved = self.directions() - 1

            self.beginRemoveRows(QtC.QModelIndex(), firstRemoved, lastRemoved)

            removedIcons = self.state.icons[firstRemoved:lastRemoved + 1]
            removedDelays = self.state.delays[firstRemoved:lastRemoved + 1]

            self.state.icons = self.state.icons[0:firstRemoved]
            self.state.delays = self.state.delays[0:firstRemoved]

            self.state.directions = directions

            self.endRemoveRows()

            return (removedIcons, removedDelays)
        else:
            firstInsertion = self.directions()
            lastInsertion = directions - 1

            self.beginInsertRows(QtC.QModelIndex(), firstInsertion, lastInsertion)


            # Basically, we extend the short list into the longer list by iterating
            # over the elements and copying each one until we have the size of list
            # we want
            dirIndex = 0

            for i in range(firstInsertion, directions):
                self.state.icons.insert(i, [ im.copy() for im in self.state.icons[dirIndex]])
                self.state.delays.insert(i, [ delay for delay in self.state.delays[dirIndex]])
                dirIndex = (dirIndex + 1) % (firstInsertion)

            self.state.directions = directions

            self.endInsertRows()

            return ([], [])

    # Model functions

    def rowCount(self, _parent):
        return self.directions()

    def columnCount(self, _parent):
        longestDirection = 0

        for i in range(self.directions()):
            longestDirection = max(longestDirection, len(self.state.icons[i]))

        return longestDirection + 1

    def index(self, row, column, parent=QtC.QModelIndex()):
        if column < self.columnCount(parent) and row < self.rowCount(parent):
            return self.createIndex(row, column)
        return QtC.QModelIndex()

    def data(self, index, role=QtC.Qt.DisplayRole):
        dirFrame = self.getDirFrame(index)

        if dirFrame is not None:
            (direction, frame) = dirFrame
            frameInfo = self.frames(direction)[frame]
            
            if role == QtC.Qt.DisplayRole or role == QtC.Qt.EditRole:
                return frameInfo[1] # The delay
            if role == QtC.Qt.DecorationRole:
                image = frameInfo[0]

                framePixmap = QtG.QPixmap.fromImage(PILQt.ImageQt(image))
                framePixmap = framePixmap.scaled(iconSize)
                frameIcon = QtG.QIcon(framePixmap)

                return frameIcon
            if role == ImageRole:
                return frameInfo[0]
        else:
            if index.column() == self.summaryColumn():
                if role == QtC.Qt.DecorationRole:
                    # Some directions may have no animation
                    currentAnim = self.animations[index.row()]
                    if currentAnim is None:
                        return None

                    # and while the animation *should* never refer to the summary column
                    # it might do if data is fetched between the column being removed
                    # and the new animation being created
                    currentFrame = currentAnim.currentAnimation()
                    if currentFrame is not None and currentFrame.index.column() != self.summaryColumn():
                        return self.data(currentFrame.index, role)
                if role == QtC.Qt.DisplayRole:
                    return ''
            return None

    # TODO: Nice icons for directions
    def headerData(self, section, orientation, role=QtC.Qt.DisplayRole):
        if orientation == QtC.Qt.Vertical:
            if self.rowCount(QtC.QModelIndex()) == 1:
                if role == QtC.Qt.DisplayRole:
                    return 'All'
                return None
            else:
                if role == QtC.Qt.DisplayRole:
                    if section == 0:
                        return 'South'
                    if section == 1:
                        return 'North'
                    if section == 2:
                        return 'East'
                    if section == 3:
                        return 'West'
                    if section == 4:
                        return 'South East'
                    if section == 5:
                        return 'South West'
                    if section == 6:
                        return 'North East'
                    if section == 7:
                        return 'North West'
                return None
        else:
            if section > self.columnCount(QtC.QModelIndex()):
                return None

            if role == QtC.Qt.DisplayRole:
                if section == self.summaryColumn():
                    return 'Animated'
                return f'Frame {section + 1}'
            return None

    def flags(self, index):
        if self.getDirFrame(index) is not None:
            return QtC.Qt.ItemIsSelectable | QtC.Qt.ItemIsEditable | QtC.Qt.ItemIsEnabled | QtC.Qt.ItemNeverHasChildren
        if index.column() == self.summaryColumn():
            return QtC.Qt.ItemNeverHasChildren | QtC.Qt.ItemIsEnabled
        return QtC.Qt.ItemNeverHasChildren

    def setData(self, index, value, role=QtC.Qt.EditRole):
        dirFrame = self.getDirFrame(index)

        if dirFrame is None:
            return False

        (direction, frame) = dirFrame

        if role == QtC.Qt.EditRole:
            if isinstance(value, str):
                try:
                    value = float(value)
                except ValueError:
                    return False

            if self.setDelay(direction, frame, value):
                self.dataChanged.emit(index, index)
                return True
            return False

        if role == ImageRole:
            self.setImage(direction, frame, value)
            self.dataChanged.emit(index, index)
            return True

        return False

    def frameDataChanged(self, topLeft, bottomRight, roles=list()):
        # Some data has changed - so we need to regenerate the
        # animations in the summary. First, we calculate which
        # rows are different now

        if (topLeft.column() < self.summaryColumn()):
            # +1, because these are inclusive and range is exclusive
            rowsChanged = range(topLeft.row(), bottomRight.row() + 1)

            self.recalculateSummary(rowsChanged)
    
    def summaryColumn(self):
        return self.columnCount(QtC.QModelIndex()) - 1

    def recalculateSummary(self, rowsChanged=None):
        numRows = self.rowCount(QtC.QModelIndex())

        if rowsChanged is None:
            rowsChanged = range(numRows)

        numAnims = len(self.animations)
        if numAnims != numRows:
            if numAnims > numRows:
                self.animations = self.animations[0:numRows]
            else:
                self.animations = self.animations + ([None] * (numRows - numAnims))

        for rowIndex in rowsChanged:
            self.generateAnimation(rowIndex)

    def generateAnimation(self, row):
        animGroup = QtC.QSequentialAnimationGroup(parent=self)

        for column in range(self.columnCount(QtC.QModelIndex())):
            currentIndex = self.index(row, column)

            frameDelay = self.data(currentIndex, role=QtC.Qt.DisplayRole)
            if isinstance(frameDelay, float):
                animGroup.addAnimation(SummaryFrame(currentIndex, frameDelay, parent=self))
            else:
                break

        previousAnim = self.animations[row]
        if previousAnim is not None:
            previousAnim.stop()

        animIndex = self.index(row, self.summaryColumn(), QtC.QModelIndex())
        animGroup.currentAnimationChanged.connect(lambda _void: self.dataChanged.emit(animIndex, animIndex, [QtC.Qt.DecorationRole]))
        self.animations[row] = animGroup
        animGroup.setLoopCount(-1)
        animGroup.start()

# Special kind of animation that does nothing other than hold on to an index
# so that we can track it later
class SummaryFrame(QtC.QAbstractAnimation):
    def __init__(self, index, delay, parent=None):
        QtC.QAbstractAnimation.__init__(self, parent)
        self.index = index
        self.delay = delay

    def duration(self):
        return self.delay * 1000

    def updateCurrentTime(self, time):
        return
