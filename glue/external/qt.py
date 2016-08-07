# This file was originally from qt-helpers, for which the license is below. 
# However, it now mainly uses QtPy and provides some additional patches. Once
# these are in QtPy, we can remove this file altogether (and move the remaining)
# functions to ``glue.utils.qt``.
# 
# Original license for qt-helpers:
#
# Copyright (c) 2015, Chris Beaumont and Thomas Robitaille
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of the Glue project nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# This file includes code adapted from:
#
#   * IPython, which is released under the modified BSD license
#     (https://github.com/ipython/ipython/blob/master/COPYING.rst)
#
#   * python_qt_binding, which is released under the BSD license
#     (https://pypi.python.org/pypi/python_qt_binding)
#
# See also this discussion
#
# http://qt-project.org/wiki/Differences_Between_PySide_and_PyQt


from __future__ import absolute_import, division, print_function

__all__ = ['get_qapp', 'load_ui']

from qtpy import QtCore, QtGui, QtWidgets, PYSIDE, PYQT4, PYQT5


def load_ui(path, parent=None, custom_widgets=None):
    if PYSIDE:
        return _load_ui_pyside(path, parent, custom_widgets=custom_widgets)
    elif PYQT5:
        return _load_ui_pyqt5(path, parent)
    else:
        return _load_ui_pyqt4(path, parent)


def _load_ui_pyside(path, parent, custom_widgets=None):
    from PySide import loadUi
    if custom_widgets is not None:
        custom_widgets = dict((widget.__name__, widget) for widget in custom_widgets)
    return loadUi(path, parent, customWidgets=custom_widgets)


def _load_ui_pyqt4(path, parent):
    from PyQt4.uic import loadUi
    return loadUi(path, parent)


def _load_ui_pyqt5(path, parent):
    from PyQt5.uic import loadUi
    return loadUi(path, parent)


qapp = None

def get_qapp(icon_path=None):
    global qapp
    qapp = QtWidgets.QApplication.instance()
    if qapp is None:
        qapp = QtWidgets.QApplication([''])
        qapp.setQuitOnLastWindowClosed(True)
        if icon_path is not None:
            qapp.setWindowIcon(QIcon(icon_path))

    # Make sure we use high resolution icons with PyQt5 for HDPI
    # displays. TODO: check impact on non-HDPI displays.
    if PYQT5:
        qapp.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps)

    return qapp


def patch_qcombobox():

    # In PySide, using Python objects as userData in QComboBox causes
    # Segmentation faults under certain conditions. Even in cases where it
    # doesn't, findData does not work correctly. Likewise, findData also
    # does not work correctly with Python objects when using PyQt4. On the
    # other hand, PyQt5 deals with this case correctly. We therefore patch
    # QComboBox when using PyQt4 and PySide to avoid issues.

    class userDataWrapper(QtCore.QObject):
        def __init__(self, data, parent=None):
            super(userDataWrapper, self).__init__(parent)
            self.data = data

    _addItem = QtWidgets.QComboBox.addItem

    def addItem(self, *args, **kwargs):
        if len(args) == 3 or (not isinstance(args[0], QtGui.QIcon)
                              and len(args) == 2):
            args, kwargs['userData'] = args[:-1], args[-1]
        if 'userData' in kwargs:
            kwargs['userData'] = userDataWrapper(kwargs['userData'],
                                                 parent=self)
        _addItem(self, *args, **kwargs)

    _insertItem = QtWidgets.QComboBox.insertItem

    def insertItem(self, *args, **kwargs):
        if len(args) == 4 or (not isinstance(args[1], QtGui.QIcon)
                              and len(args) == 3):
            args, kwargs['userData'] = args[:-1], args[-1]
        if 'userData' in kwargs:
            kwargs['userData'] = userDataWrapper(kwargs['userData'],
                                                 parent=self)
        _insertItem(self, *args, **kwargs)

    _setItemData = QtWidgets.QComboBox.setItemData

    def setItemData(self, index, value, role=QtCore.Qt.UserRole):
        value = userDataWrapper(value, parent=self)
        _setItemData(self, index, value, role=role)

    _itemData = QtWidgets.QComboBox.itemData

    def itemData(self, index, role=QtCore.Qt.UserRole):
        userData = _itemData(self, index, role=role)
        if isinstance(userData, userDataWrapper):
            userData = userData.data
        return userData

    def findData(self, value):
        for i in range(self.count()):
            if self.itemData(i) == value:
                return i
        return -1

    QtWidgets.QComboBox.addItem = addItem
    QtWidgets.QComboBox.insertItem = insertItem
    QtWidgets.QComboBox.setItemData = setItemData
    QtWidgets.QComboBox.itemData = itemData
    QtWidgets.QComboBox.findData = findData


def patch_loadui():

    # In PySide, loadUi does not exist, so we define it using QUiLoader, and
    # then make sure we expose that function. This is based on the solution at
    #
    # https://gist.github.com/cpbotha/1b42a20c8f3eb9bb7cb8
    #
    # which was released under the MIT license:
    #
    # Copyright (c) 2011 Sebastian Wiesner <lunaryorn@gmail.com>
    # Modifications by Charl Botha <cpbotha@vxlabs.com>
    #
    # Permission is hereby granted, free of charge, to any person obtaining a
    # copy of this software and associated documentation files (the "Software"),
    # to deal in the Software without restriction, including without limitation
    # the rights to use, copy, modify, merge, publish, distribute, sublicense,
    # and/or sell copies of the Software, and to permit persons to whom the
    # Software is furnished to do so, subject to the following conditions:
    #
    # The above copyright notice and this permission notice shall be included in
    # all copies or substantial portions of the Software.
    #
    # THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    # IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    # FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
    # THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    # LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    # FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    # DEALINGS IN THE SOFTWARE.
    #
    # This version includes further changes.

    from PySide.QtCore import Slot, QMetaObject
    from PySide.QtUiTools import QUiLoader
    from PySide.QtGui import QApplication, QMainWindow, QMessageBox

    class UiLoader(QUiLoader):
        """
        Subclass of :class:`~PySide.QtUiTools.QUiLoader` to create the user
        interface in a base instance.

        Unlike :class:`~PySide.QtUiTools.QUiLoader` itself this class does not
        create a new instance of the top-level widget, but creates the user
        interface in an existing instance of the top-level class if needed.

        This mimics the behaviour of :func:`PyQt4.uic.loadUi`.
        """

        def __init__(self, baseinstance, customWidgets=None):
            """
            Create a loader for the given ``baseinstance``.

            The user interface is created in ``baseinstance``, which must be an
            instance of the top-level class in the user interface to load, or a
            subclass thereof.

            ``customWidgets`` is a dictionary mapping from class name to class
            object for custom widgets. Usually, this should be done by calling
            registerCustomWidget on the QUiLoader, but with PySide 1.1.2 on
            Ubuntu 12.04 x86_64 this causes a segfault.

            ``parent`` is the parent object of this loader.
            """

            QUiLoader.__init__(self, baseinstance)
            self.baseinstance = baseinstance
            self.customWidgets = customWidgets

        def createWidget(self, class_name, parent=None, name=''):
            """
            Function that is called for each widget defined in ui file,
            overridden here to populate baseinstance instead.
            """

            if parent is None and self.baseinstance:
                # supposed to create the top-level widget, return the base
                # instance instead
                return self.baseinstance

            else:

                # For some reason, Line is not in the list of available
                # widgets, but works fine, so we have to special case it here.
                if class_name in self.availableWidgets() or class_name == 'Line':
                    # create a new widget for child widgets
                    widget = QUiLoader.createWidget(self, class_name, parent, name)

                else:
                    # if not in the list of availableWidgets, must be a custom
                    # widget this will raise KeyError if the user has not
                    # supplied the relevant class_name in the dictionary, or
                    # TypeError, if customWidgets is None
                    try:
                        widget = self.customWidgets[class_name](parent)
                    except (TypeError, KeyError) as e:
                        raise Exception('No custom widget ' + class_name + ' '
                                        'found in customWidgets')

                if self.baseinstance:
                    # set an attribute for the new child widget on the base
                    # instance, just like PyQt4.uic.loadUi does.
                    setattr(self.baseinstance, name, widget)

                return widget

    def loadUi(uifile, baseinstance=None, customWidgets=None,
               workingDirectory=None):
        """
        Dynamically load a user interface from the given ``uifile``.

        ``uifile`` is a string containing a file name of the UI file to load.

        If ``baseinstance`` is ``None``, the a new instance of the top-level
        widget will be created. Otherwise, the user interface is created within
        the given ``baseinstance``. In this case ``baseinstance`` must be an
        instance of the top-level widget class in the UI file to load, or a
        subclass thereof. In other words, if you've created a ``QMainWindow``
        interface in the designer, ``baseinstance`` must be a ``QMainWindow``
        or a subclass thereof, too. You cannot load a ``QMainWindow`` UI file
        with a plain :class:`~PySide.QtGui.QWidget` as ``baseinstance``.

        ``customWidgets`` is a dictionary mapping from class name to class
        object for custom widgets. Usually, this should be done by calling
        registerCustomWidget on the QUiLoader, but with PySide 1.1.2 on Ubuntu
        12.04 x86_64 this causes a segfault.

        :method:`~PySide.QtCore.QMetaObject.connectSlotsByName()` is called on
        the created user interface, so you can implemented your slots according
        to its conventions in your widget class.

        Return ``baseinstance``, if ``baseinstance`` is not ``None``. Otherwise
        return the newly created instance of the user interface.
        """

        loader = UiLoader(baseinstance, customWidgets)

        if workingDirectory is not None:
            loader.setWorkingDirectory(workingDirectory)

        widget = loader.load(uifile)
        QMetaObject.connectSlotsByName(widget)
        return widget

    import PySide
    PySide.loadUi = loadUi


# We patch this only now, once QtCore and QtGui are defined
if PYSIDE or PYQT4:
    patch_qcombobox()

# For PySide, we need to create a loadUi function
if PYSIDE:
    patch_loadui()
