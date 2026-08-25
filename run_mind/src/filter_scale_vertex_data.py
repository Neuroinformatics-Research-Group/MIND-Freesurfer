
def filter_vertex_data(vertex_data, features_manual_list, features_generated_list,
                       vertices2filter = ('CT', 'Vol', 'SA'),
                       filter_vertices=True):
    columns = ['Label'] + list(features_generated_list)
    feature_conv_dict = dict(zip(features_manual_list, features_generated_list))

    vertex_data_clean = vertex_data.copy()

    if filter_vertices:
        #for feat in ('CT', 'Vol', 'SA'):
        for feat in vertices2filter:
            if feat in features_manual_list:
                col = feature_conv_dict[feat]
                vertex_data_clean = vertex_data_clean[vertex_data_clean[col] != 0]

    vertex_data_clean = vertex_data_clean[columns]
    n_removed_vertices = len(vertex_data) - len(vertex_data_clean)

    return vertex_data_clean, n_removed_vertices

def scale_vertex_data(vertex_data):
    # grab the features you have in your data (we ignore column 0 because that is our ROI label data)
    features2scaleby = list(vertex_data.columns[1:])

    # make copy of vertex data to store out the z scaled data
    vertex_data_z = vertex_data.copy()

    # standardize across the brain for each feature to get each dimension to roughly the same scale.
    for x in features2scaleby:
        vertex_data_z[x] = (vertex_data[x] - vertex_data[x].mean()) / vertex_data[x].std()

    return vertex_data_z
