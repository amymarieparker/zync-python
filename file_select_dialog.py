"""Dialog to select files or directories
"""

import glob
import os
import re

# Try importing from PySide (Maya 2016) first, then from PySide2 (Maya 2017)
# Alias the classes since some of them have been moved from PyGui to PyWidgets
try:
  import pysideuic
  import PySide.QtGui
  import PySide.QtCore as QtCore

  QDialog = PySide.QtGui.QDialog
  QDir = QtCore.QDir
  QDialogButtonBox = PySide.QtGui.QDialogButtonBox
  QFileSystemModel = PySide.QtGui.QFileSystemModel
  QHeaderView = PySide.QtGui.QHeaderView
  QTreeView = PySide.QtGui.QTreeView
  QPushButton = PySide.QtGui.QPushButton

  pysideVersion = PySide.__version__
except:
  import pyside2uic as pysideuic
  import PySide2.QtCore as QtCore
  import PySide2.QtWidgets

  QDialog = PySide2.QtWidgets.QDialog
  QDir = QtCore.QDir
  QDialogButtonBox = PySide2.QtWidgets.QDialogButtonBox
  QFileSystemModel = PySide2.QtWidgets.QFileSystemModel
  QHeaderView = PySide2.QtWidgets.QHeaderView
  QTreeView = PySide2.QtWidgets.QTreeView
  QPushButton = PySide2.QtWidgets.QPushButton

  pysideVersion = PySide2.__version__


import dialog_helper

from settings import Settings

UI_SELECT_FILES = '%s/resources/select_files_dialog.ui' % os.path.dirname(__file__)
UI_ICON_FILE_STEM = '%s/resources/%%s' % os.path.dirname(__file__)

class CheckableDirModel(QFileSystemModel):
  """Extends QDirModel by adding checkboxes next to files and
  directories. Stores the files and directories selected."""

  def __init__(self, selected_files):
    super(CheckableDirModel, self).__init__(None)
    if 'MacintoshVersion' in dir(QtCore.QSysInfo):
      # This attrocity is the only way to make QFileSystemModel report /Volumes
      # on Mac. Contrary to what the documentation says
      # https://srinikom.github.io/pyside-docs/PySide/QtGui/QFileSystemModel.html#PySide.QtGui.PySide.QtGui.QFileSystemModel.setRootPath
      # this causes the /Volumes path to appear in the list
      self.setRootPath('/Volumes')
    else:
      self.setRootPath(QDir.currentPath())
    self.files = self._init_files(selected_files)

  def set_tree_view(self, tree_view):
    self.tree_view = tree_view

  def get_selected_files(self):
    selected_files = []
    for filename, status in self.files.items():
      if status == QtCore.Qt.Checked:
        selected_files.append(filename)
    return selected_files

  def flags(self, index):
    return QFileSystemModel.flags(self, index) | QtCore.Qt.ItemIsUserCheckable

  def data(self, index, role=QtCore.Qt.DisplayRole):
    if role == QtCore.Qt.CheckStateRole and index.column() == 0:
      # In QTreeView once can add checkboxes for all columns
      # here we only do it for the first where there is an icon
      # and file/folder name
      filename = self.filePath(index)
      if self.files.get(filename, QtCore.Qt.Unchecked) == QtCore.Qt.PartiallyChecked:
        return QtCore.Qt.PartiallyChecked
      else:
        return self._getCheckStatus(filename)
    else:
      return QFileSystemModel.data(self, index, role)

  def setData(self, index, value, role):
    if role == QtCore.Qt.CheckStateRole and index.column() == 0:
      filename = self.filePath(index)

      self._clearDown(filename)
      if self._getCheckStatus(filename) == QtCore.Qt.Checked:
        if self.files.get(filename, QtCore.Qt.Unchecked) == QtCore.Qt.Unchecked:
          self._setStatusSideways(filename, QtCore.Qt.Checked)
        self.files[filename] = QtCore.Qt.Unchecked
      else:
        self.files[filename] = QtCore.Qt.Checked
      self._propagateUp(filename)

      self.emit(QtCore.SIGNAL("dataChanged(QModelIndex,QModelIndex)"), None, None)

      return True
    else:
      return QFileSystemModel.setData(self, index, value, role)

  @staticmethod
  def _init_files(selected_files):
    files = {}
    sorted_files = sorted(selected_files)
    for file in sorted_files:
      files[file] = QtCore.Qt.Checked
      while True:
        dir, basename = os.path.split(file)
        if dir == file:
          break
        if not dir in files:
          files[dir] = QtCore.Qt.PartiallyChecked
        file = dir
    return files

  def _getCheckStatus(self, filename):
    """Gets cumulative status of a node.
    """
    check_status = self.files.get(filename, QtCore.Qt.Unchecked)
    if check_status == QtCore.Qt.Checked:
      return QtCore.Qt.Checked
    elif check_status == QtCore.Qt.PartiallyChecked:
      return QtCore.Qt.Unchecked
    else:
      dirname = os.path.dirname(filename)
      if dirname and not dirname == filename:
        return self._getCheckStatus(dirname)
      else:
        return QtCore.Qt.Unchecked

  @staticmethod
  def listDirectory(dirname):
    """Returns list of full paths to files and dirs in the given dir.
    Replaces '\' (backslash) and '\\' (double backslash) with '/' (slash)
    in returned paths to unify the path notation.
    """
    full_names = glob.glob(os.path.join(dirname, '*'))
    for idx in range(len(full_names)):
      full_names[idx] = full_names[idx].replace('\\\\', '/')
      full_names[idx] = full_names[idx].replace('\\', '/')
    return full_names

  def _setStatusSideways(self, filename, status):
    """Check all files on the same hierarchy level.
    """
    full_names = self.listDirectory(os.path.dirname(filename))
    for full_name in full_names:
      self.files[full_name] = status

  def _propagateUp(self, filename):
    """Sets the status up the hierarchy.
    """
    dirname = os.path.dirname(filename)
    if dirname == filename or not dirname:
      return
    full_names = self.listDirectory(dirname)

    num_checked = 0
    num_unchecked = 0
    for full_name in full_names:
      status = self.files.get(full_name, QtCore.Qt.Unchecked)
      num_checked += 1 if status == QtCore.Qt.Checked else 0
      num_unchecked += 1 if status == QtCore.Qt.Unchecked else 0
    if num_checked == len(full_names):
      self.files[dirname] = QtCore.Qt.Checked
      self._setStatusSideways(filename, QtCore.Qt.Unchecked)
    elif num_unchecked == len(full_names):
      self.files[dirname] = QtCore.Qt.Unchecked
    else:
      self.files[dirname] = QtCore.Qt.PartiallyChecked

    self._propagateUp(dirname)

  def _clearDown(self, filename):
    """Clears check status for all elements down the hierarchy.
    """
    if not filename in self.files or not os.path.isdir(filename):
      return
    full_names = self.listDirectory(filename)
    for full_name in full_names:
      if full_name in self.files:
        del self.files[full_name]
      self._clearDown(full_name)


class FileSelectDialog(object):
  """Displays dialog allowing user to select files or directories"""
  def __init__(self, project_name, parent=None):
    """Constructs file selection dialog

    Params:
      project_name: str, name of Zync project
    """
    self.settings = Settings.get()
    self.project_name = project_name

    FormClass = dialog_helper.load_ui_type(UI_SELECT_FILES)
    form_class = FormClass()
    self.dialog = QDialog()
    self.parent_qt_window = parent
    if parent:
      self.dialog.setParent(parent, QtCore.Qt.Window)
    form_class.setupUi(self.dialog)

    selected_files = set(self.settings.get_aux_files(project_name))
    self.model = CheckableDirModel(selected_files)
    tree_view = self.dialog.findChild(QTreeView, 'listDirsFiles')
    self.model.set_tree_view(tree_view)
    tree_view.setModel(self.model)
    style = ("""
        QTreeView::indicator:unchecked { image: url('%s'); }
        QTreeView::indicator:indeterminate { image: url('%s'); }
        QTreeView::indicator:checked { image: url('%s'); }
        QTreeView::item {
          border-top-color: transparent;
          border-bottom-color: transparent;}""" %
             (UI_ICON_FILE_STEM % 'unchecked.png',
              UI_ICON_FILE_STEM % 'indeterminate.png',
              UI_ICON_FILE_STEM % 'checked.png'))
    tree_view.setStyleSheet(style.replace('\\', '/'))
    header = tree_view.header()
    if re.match("1\.*", pysideVersion):
      header.setResizeMode(QHeaderView.Interactive)
    else:
      header.setSectionResizeMode(QHeaderView.Interactive)
    header.resizeSection(0, 300)
    header.resizeSection(1, 65)
    header.resizeSection(2, 65)

    button_box = self.dialog.findChild(QDialogButtonBox, 'buttonBox')
    button_box.accepted.connect(self.accepted)
    button_box.rejected.connect(self.rejected)

    expand_files_button = self.dialog.findChild(QPushButton, 'expandFiles')
    expand_files_button.clicked.connect(self.expand_files)

  def expand_files(self):
    selected_files = self.model.get_selected_files()
    for filename in selected_files:
      index = self.model.index(filename)
      parent = index.parent()
      while parent.isValid():
        self.model.tree_view.expand(parent)
        parent = parent.parent()

  @staticmethod
  def get_extra_assets(new_project_name):
    expanded_files = []
    def expand_selected_files(selected_files, expanded_files):
      for filename in selected_files:
        if os.path.isdir(filename):
          expand_selected_files(CheckableDirModel.listDirectory(filename), expanded_files)
        else:
          expanded_files.append(filename)
    selected_files = Settings.get().get_aux_files(new_project_name)
    expand_selected_files(selected_files, expanded_files)

    return expanded_files

  def accepted(self):
    selected_files = self.model.get_selected_files()
    self.settings.put_aux_files(self.project_name, selected_files)
    if not self.parent_qt_window:
      self.dialog.destroy()
    else:
      self.dialog.accept()
    self.dialog = None

  def rejected(self):
    if not self.parent_qt_window:
      self.dialog.destroy()
    else:
      self.dialog.reject()
    self.dialog = None

  def show(self):
    self.dialog.show()

  def exec_(self):
    self.dialog.exec_()


