#!/usr/bin/env python
# encoding: utf-8

import sys, os
import xml.etree.ElementTree as ElementTree
import xml.dom.minidom as minidom

if len(sys.argv) < 2 or len(sys.argv) % 2 != 0:
    print("./replaceHadoopProperty <file> <name1> <value1> <name2> <value2> ...")

fileName = sys.argv[1]
propertyNames = sys.argv[2::2]
propertyValues = sys.argv[3::2]
replaced = [False] * len(propertyNames)

print(propertyNames)
print(propertyValues)

root = None

try:
    tree = ElementTree.parse(fileName)
    root = tree.getroot()
except Exception:
    configurationElement = ElementTree.Element("configuration")
    tree = ElementTree.ElementTree(configurationElement)
    root = tree.getroot()

for prop in root.iter('property'):
    children = {child.tag: child for child in prop}

    try:
        index = propertyNames.index(children['name'].text)
        children['value'].text = propertyValues[index]
        replaced[index] = True
    except Exception as e:
        print(str(e))
        pass

for i, propertyReplaced in enumerate(replaced):
    if not propertyReplaced:
        newProperty = ElementTree.SubElement(root, "property")
        newPropertyName = ElementTree.SubElement(newProperty, "name")
        newPropertyName.text = propertyNames[i]
        newPropertyValue = ElementTree.SubElement(newProperty, "value")
        newPropertyValue.text = propertyValues[i]

def prettify(elem):
    """Return a pretty-printed XML string for the Element.
    """
    rough_string = ElementTree.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    pretty =  reparsed.toprettyxml(indent="\t")
    return "\n".join([line for line in pretty.split('\n') if line.strip() != ''])

with open(fileName, "w") as f:
    f.write(prettify(root))
